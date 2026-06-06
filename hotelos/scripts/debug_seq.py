import sys
from pathlib import Path
import asyncio
from httpx import AsyncClient, ASGITransport
# ensure project root is on sys.path for local imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hotelos.broker import InMemoryBroker, set_broker_instance
set_broker_instance(InMemoryBroker())
from main import app

async def run():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        r = await client.get('/api/reception/rooms')
        print('rooms status', r.status_code, r.json())
        r = await client.post('/api/reception/checkin', params={'name':'Test Guest'})
        print('checkin', r.status_code, r.json())
        guest = r.json().get('guest')
        r = await client.post('/api/roomservice/order', params={'room_number': guest['room'], 'items': 'Tea'})
        print('order', r.status_code, r.json())
        r = await client.post('/api/maintenance/report', params={'room_number': guest['room'], 'description':'Light out', 'urgency':1})
        print('maintenance report', r.status_code, r.text)

asyncio.run(run())
