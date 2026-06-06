HotelOS — simplified microservices demo

Stack
- Python 3.10+
- FastAPI
- Redis (Pub/Sub)
- Uvicorn

Run (requires Redis running locally on default port 6379):

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Quick Redis options
- Docker (recommended):

```bash
# from project root
docker compose up -d redis
# then start the app
python -m uvicorn main:app --reload --port 8000
```

- Local Redis (Windows):

Install Redis via MSOpenTech builds or use WSL. Then start the server:

```powershell
redis-server.exe
```

- WSL (Ubuntu):

```bash
sudo apt update
sudo apt install redis-server
sudo service redis-server start
```

Tips
- If Redis is not available the app automatically falls back to an in-memory broker for demo and tests.
- Open the dashboard after starting the server at `http://127.0.0.1:8000/dashboard` or use the login at `/login` (token is `hotelos-secret`).

Endpoints
- Reception, Housekeeping, Room Service, Maintenance mounted under `/api/*`
- Dashboard: `/dashboard` (open in browser)

Files of interest:
- `broker.py` — Redis broker wrapper
- `services/*.py` — microservice routers
- `main.py` — app assembly and WebSocket dashboard
- `events.md` — event list and payloads
- `data_structures.md` — choice justification
