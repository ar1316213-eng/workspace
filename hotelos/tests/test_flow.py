import pytest
from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_end_to_end(monkeypatch):
    # use in-memory broker to avoid Redis dependency
    from hotelos.broker import InMemoryBroker, set_broker_instance
    set_broker_instance(InMemoryBroker())

    # import app after setting broker
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        # check rooms
        r = await client.get('/api/reception/rooms')
        assert r.status_code == 200
        data = r.json()
        assert 'rooms' in data

        # checkin (explicit room selection required)
        r = await client.post('/api/reception/checkin', params={'name':'Test Guest', 'room_number': 1})
        assert r.status_code == 200
        guest = r.json().get('guest')
        assert guest and 'id' in guest

        # explicit room assignment
        r = await client.post('/api/reception/checkin', params={'name':'Reserved Guest', 'room_number': 2})
        assert r.status_code == 200
        reserved = r.json().get('guest')
        assert reserved and reserved['room'] == 2

        # place order
        r = await client.post('/api/roomservice/order', params={'room_number': guest['room'], 'items': 'Tea'})
        assert r.status_code == 200
        order = r.json()
        assert order['state'] == 'Received'

        # verify room service is not allowed on an unoccupied room
        r = await client.post('/api/roomservice/order', params={'room_number': 3, 'items': 'Napkin'})
        assert r.status_code == 400

        # checkout guest, dirty the room, and start housekeeping
        r = await client.post('/api/reception/checkout', params={'guest_id': guest['id']})
        assert r.status_code == 200
        bill = r.json().get('bill')
        assert bill and bill['guest_id'] == guest['id']
        assert bill['room_charge'] >= 100.0
        assert bill['service_charge'] == 10.0

        r = await client.post('/api/housekeeping/mark_cleaning', params={'room_number': 1})
        assert r.status_code == 200
        assert r.json()['status'] == 'Being cleaned'

        r = await client.post('/api/housekeeping/mark_clean', params={'room_number': 1})
        assert r.status_code == 200
        assert r.json()['status'] == 'Clean'

        # report maintenance
        r = await client.post('/api/maintenance/report', params={'room_number': reserved['room'], 'description':'Light out', 'urgency':1})
        assert r.status_code == 200
        issue = r.json()
        assert issue['urgency'] == 1
