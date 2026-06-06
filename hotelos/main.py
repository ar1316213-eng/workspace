import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, WebSocket, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

ROOT = Path(__file__).resolve().parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from hotelos.broker import get_broker, InMemoryBroker, set_broker_instance
from hotelos.services import reception, housekeeping, room_service, maintenance

# Global broker and internal event queue used for broadcasting to dashboard
broker = None
event_queue: asyncio.Queue = asyncio.Queue()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global broker
    broker = get_broker()
    try:
        if not await broker.ping():
            raise RuntimeError("Redis unavailable")
    except Exception:
        print("Redis not available; using in-memory broker for demo mode")
        set_broker_instance(InMemoryBroker())
        broker = get_broker()

    channels = [
        'room_assigned', 'room_vacated', 'housekeeping_status', 'housekeeping_queue_updated',
        'room_service_event', 'maintenance_reported', 'maintenance_assigned', 'maintenance_resolved',
        'billing_event'
    ]
    app.state.redis_listener = asyncio.create_task(broker.subscribe_to_channels(channels, event_queue))
    app.state.broadcast_task = asyncio.create_task(broadcast_events())
    try:
        yield
    finally:
        app.state.redis_listener.cancel()
        app.state.broadcast_task.cancel()
        await broker.close()

app = FastAPI(lifespan=lifespan)
app.include_router(reception.router, prefix="/api/reception")
app.include_router(housekeeping.router, prefix="/api/housekeeping")
app.include_router(room_service.router, prefix="/api/roomservice")
app.include_router(maintenance.router, prefix="/api/maintenance")

static_dir = str(Path(__file__).resolve().parent / 'static')
app.mount('/static', StaticFiles(directory=static_dir), name='static')

dashboard_path = Path(__file__).resolve().parent / 'templates' / 'dashboard.html'
ADMIN_TOKEN = 'hotelos-secret'
COOKIE_NAME = 'hotelos_token'
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('hotelos')

def verify_auth_token(token: str | None) -> bool:
    return token == ADMIN_TOKEN

async def get_dashboard_token(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not verify_auth_token(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')
    return token

@app.get('/login')
async def login_form():
    return HTMLResponse(
        '<!doctype html><html><head><meta charset="utf-8"><title>HotelOS Login</title></head>'
        '<body><h1>HotelOS Login</h1><form method="post" action="/login">'
        '<label>Token: <input name="token" type="password" required></label><br><br>'
        '<button type="submit">Login</button></form></body></html>'
    )

@app.post('/login')
async def login_submit(token: str = Form(...)):
    if not verify_auth_token(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')
    response = RedirectResponse(url='/dashboard', status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(COOKIE_NAME, token, httponly=True)
    return response

@app.post('/logout')
async def logout():
    response = RedirectResponse(url='/login', status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(COOKIE_NAME)
    return response

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning('HTTP error %s: %s', request.url.path, exc.detail)
    return JSONResponse({'detail': exc.detail}, status_code=exc.status_code)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning('Validation error for %s: %s', request.url.path, exc.errors())
    return JSONResponse({'detail': 'Invalid request data'}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception('Unhandled exception on %s', request.url.path)
    return JSONResponse({'detail': 'Internal server error'}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@app.get('/dashboard')
async def get_dashboard(request: Request, token: str = Depends(get_dashboard_token)):
    return HTMLResponse(dashboard_path.read_text(encoding='utf-8'))

# websocket endpoint for dashboard
clients: set[WebSocket] = set()

@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.cookies.get(COOKIE_NAME) or websocket.query_params.get('token')
    if not verify_auth_token(token):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            # keep connection alive; dashboard is push-only
            await asyncio.sleep(10)
    except Exception:
        pass
    finally:
        clients.remove(websocket)

async def broadcast_events():
    # aggregate state snapshots and push to clients periodically
    state = {
        'rooms': None,
        'orders': None,
        'issues': None,
        'guests': None
    }
    try:
        while True:
            # consume available events
            try:
                ev = await asyncio.wait_for(event_queue.get(), timeout=1.0)
            except asyncio.CancelledError:
                logger.info('broadcast_events task cancelled')
                break
            except (asyncio.TimeoutError, TimeoutError):
                ev = None

            if ev is not None:
                ch = ev.get('channel')
                payload = ev.get('payload')
                # map channels to state updates
                if ch in ('room_assigned', 'room_vacated', 'housekeeping_status'):
                    # fetch rooms snapshot from reception
                    import httpx
                    try:
                        r = await httpx.get('http://127.0.0.1:8000/api/reception/rooms', timeout=1.0)
                        raw_rooms = r.json().get('rooms', [])
                        state['rooms'] = {'rooms': raw_rooms}
                    except Exception:
                        logger.exception('Failed to refresh room snapshot')
                if ch == 'room_service_event':
                    import httpx
                    try:
                        r = await httpx.get('http://127.0.0.1:8000/api/roomservice/orders', timeout=1.0)
                        state['orders'] = r.json()
                    except Exception:
                        logger.exception('Failed to refresh room service orders')
                if ch.startswith('maintenance'):
                    import httpx
                    try:
                        r = await httpx.get('http://127.0.0.1:8000/api/maintenance/open', timeout=1.0)
                        state['issues'] = r.json()
                    except Exception:
                        logger.exception('Failed to refresh maintenance issues')
            # guests
            try:
                if state['rooms']:
                    guests = []
                    for room in state['rooms'].get('rooms', []):
                        guest = room.get('guest')
                        if isinstance(guest, dict):
                            guests.append({'name': guest.get('name'), 'room': guest.get('room')})
                    state['guests'] = guests
            except Exception:
                logger.exception('Failed to build guest visit state')

            # push to websocket clients
            for ws in list(clients):
                try:
                    if state['rooms'] is not None:
                        await ws.send_json({'type': 'rooms', 'payload': state['rooms']})
                    if state['orders'] is not None:
                        await ws.send_json({'type': 'orders', 'payload': state['orders']})
                    if state['issues'] is not None:
                        await ws.send_json({'type': 'issues', 'payload': state['issues']})
                    if state['guests'] is not None:
                        await ws.send_json({'type': 'guests', 'payload': state['guests']})
                except Exception:
                    clients.remove(ws)
        else:
            # periodically send full state even without events
            for ws in list(clients):
                try:
                    if state['rooms'] is not None:
                        await ws.send_json({'type': 'rooms', 'payload': state['rooms']})
                    if state['orders'] is not None:
                        await ws.send_json({'type': 'orders', 'payload': state['orders']})
                    if state['issues'] is not None:
                        await ws.send_json({'type': 'issues', 'payload': state['issues']})
                    if state['guests'] is not None:
                        await ws.send_json({'type': 'guests', 'payload': state['guests']})
                except Exception:
                    clients.remove(ws)
            await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        logger.info('broadcast_events outer cancellation received')
    finally:
        logger.info('broadcast_events stopped')

if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000, reload=True)
