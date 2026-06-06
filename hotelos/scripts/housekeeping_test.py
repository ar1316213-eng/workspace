import asyncio
import sys
sys.path.insert(0, r'c:\workspace\hotelos')
from httpx import AsyncClient, ASGITransport
import broker
from main import app

async def run():
    broker.set_broker_instance(broker.InMemoryBroker())
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        r = await client.post('/api/reception/checkin', params={'name': 'Test Guest', 'room_number': 1})
        print('checkin', r.status_code, r.text)
        guest = r.json()['guest']
        r = await client.post('/api/reception/checkout', params={'guest_id': guest['id']})
        print('checkout', r.status_code, r.text)
        r = await client.post('/api/housekeeping/mark_cleaning', params={'room_number': 1})
        print('start_clean', r.status_code, r.text)
        r = await client.post('/api/housekeeping/mark_clean', params={'room_number': 1})
        print('mark_clean', r.status_code, r.text)
        r = await client.get('/api/reception/rooms')
        print('room1 after clean', [room for room in r.json()['rooms'] if room['number'] == 1][0])

asyncio.run(run())
