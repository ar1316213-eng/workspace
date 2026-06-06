import asyncio
import httpx

BASE = "http://127.0.0.1:8000"

async def request_json(client: httpx.AsyncClient, method: str, url: str, **kwargs):
    r = await client.request(method, url, **kwargs)
    if r.is_error:
        print(f'ERROR {r.status_code} {r.url}')
        print(r.text)
        r.raise_for_status()
    try:
        return r.json()
    except ValueError:
        print(f'Invalid JSON response from {r.url}:')
        print(r.text)
        raise

async def main():
    async with httpx.AsyncClient() as client:
        print('Check in Alice')
        result = await request_json(client, 'POST', f'{BASE}/api/reception/checkin', params={'name': 'Alice'})
        print(result)
        await asyncio.sleep(0.5)

        print('Place room service order for room 1')
        r = await client.post(f'{BASE}/api/roomservice/order', params={'room_number':1, 'items':'Coffee, Sandwich'})
        print(r.json())
        await asyncio.sleep(0.5)

        print('Report maintenance for room 1')
        r = await client.post(f'{BASE}/api/maintenance/report', params={'room_number':1, 'description':'AC not cooling', 'urgency':2})
        print(r.json())
        await asyncio.sleep(0.5)

        print('Assign maintenance next')
        r = await client.post(f'{BASE}/api/maintenance/assign_next')
        print(r.json())
        await asyncio.sleep(0.5)

        print('Check housekeeping queue')
        r = await client.get(f'{BASE}/api/housekeeping/queue')
        print(r.json())

if __name__ == '__main__':
    asyncio.run(main())
