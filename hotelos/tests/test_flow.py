import pytest
from httpx import AsyncClient, ASGITransport

def setup_broker():
    """Helper to set up in-memory broker before each test"""
    from hotelos.broker import InMemoryBroker, set_broker_instance
    set_broker_instance(InMemoryBroker())

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


# ============================================================================
# NEW TEST SUITE: 10 Additional Tests
# ============================================================================

@pytest.mark.asyncio
async def test_1_authentication_required():
    """Test 1: Dashboard requires valid authentication token"""
    setup_broker()
    from main import app
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        # Access dashboard without token
        r = await client.get('/dashboard', follow_redirects=False)
        assert r.status_code == 401, "Dashboard should require authentication"
        
        # WebSocket without token should close
        with pytest.raises(Exception):
            async with client.websocket_connect('/ws'):
                pass


@pytest.mark.asyncio
async def test_2_invalid_room_number_checkin():
    """Test 2: Guest check-in validates room number (1-100 range)"""
    setup_broker()
    from main import app
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        # Invalid: room 0
        r = await client.post('/api/reception/checkin', params={'name': 'Guest', 'room_number': 0})
        assert r.status_code == 422, "Room 0 should be rejected"
        
        # Invalid: room 101 (out of range)
        r = await client.post('/api/reception/checkin', params={'name': 'Guest', 'room_number': 101})
        assert r.status_code == 422, "Room 101 should be rejected"
        
        # Valid: room 1-100 should succeed
        r = await client.post('/api/reception/checkin', params={'name': 'Valid Guest', 'room_number': 1})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_3_guest_name_validation():
    """Test 3: Guest name must be 1-128 characters"""
    setup_broker()
    from main import app
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        # Empty name should fail
        r = await client.post('/api/reception/checkin', params={'name': '', 'room_number': 1})
        assert r.status_code == 422, "Empty name should be rejected"
        
        # Name too long (129+ chars)
        long_name = 'A' * 129
        r = await client.post('/api/reception/checkin', params={'name': long_name, 'room_number': 1})
        assert r.status_code == 422, "Name > 128 chars should be rejected"
        
        # Valid name (1-128 chars)
        r = await client.post('/api/reception/checkin', params={'name': 'Valid Name', 'room_number': 1})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_4_room_service_validation():
    """Test 4: Room service orders validate items and amount"""
    setup_broker()
    from main import app
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        # Check in guest
        r = await client.post('/api/reception/checkin', params={'name': 'Guest', 'room_number': 1})
        assert r.status_code == 200
        
        # Empty items should fail
        r = await client.post('/api/roomservice/order', params={'room_number': 1, 'items': ''})
        assert r.status_code == 422, "Empty items should be rejected"
        
        # Items too long (257+ chars)
        long_items = 'X' * 257
        r = await client.post('/api/roomservice/order', params={'room_number': 1, 'items': long_items})
        assert r.status_code == 422, "Items > 256 chars should be rejected"
        
        # Negative amount should fail
        r = await client.post('/api/roomservice/order', params={'room_number': 1, 'items': 'Tea', 'amount': -5.0})
        assert r.status_code == 422, "Negative amount should be rejected"
        
        # Valid order
        r = await client.post('/api/roomservice/order', params={'room_number': 1, 'items': 'Coffee', 'amount': 5.0})
        assert r.status_code == 200
        assert r.json()['amount'] == 5.0


@pytest.mark.asyncio
async def test_5_maintenance_description_validation():
    """Test 5: Maintenance reports require 5-256 char descriptions and 1-5 urgency"""
    setup_broker()
    from main import app
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        # Description too short (< 5 chars)
        r = await client.post('/api/maintenance/report', params={'room_number': 1, 'description': 'Bad', 'urgency': 1})
        assert r.status_code == 422, "Description < 5 chars should be rejected"
        
        # Description too long (> 256 chars)
        long_desc = 'A' * 257
        r = await client.post('/api/maintenance/report', params={'room_number': 1, 'description': long_desc, 'urgency': 1})
        assert r.status_code == 422, "Description > 256 chars should be rejected"
        
        # Invalid urgency (0 or 6)
        r = await client.post('/api/maintenance/report', params={'room_number': 1, 'description': 'Broken light', 'urgency': 0})
        assert r.status_code == 422, "Urgency 0 should be rejected"
        
        r = await client.post('/api/maintenance/report', params={'room_number': 1, 'description': 'Broken light', 'urgency': 6})
        assert r.status_code == 422, "Urgency 6 should be rejected"
        
        # Valid report
        r = await client.post('/api/maintenance/report', params={'room_number': 1, 'description': 'Broken light fixture', 'urgency': 3})
        assert r.status_code == 200
        assert r.json()['urgency'] == 3


@pytest.mark.asyncio
async def test_6_room_filtering():
    """Test 6: Room list endpoint supports filtering by floor, type, status, etc."""
    setup_broker()
    from main import app
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        # Get all rooms
        r = await client.get('/api/reception/rooms')
        assert r.status_code == 200
        all_rooms = r.json()['rooms']
        assert len(all_rooms) == 10
        
        # Filter by floor
        r = await client.get('/api/reception/rooms', params={'floor': 1})
        floor1_rooms = r.json()['rooms']
        assert all(room['floor'] == 1 for room in floor1_rooms), "All rooms should be floor 1"
        assert len(floor1_rooms) == 5, "Should have 5 rooms on floor 1"
        
        # Filter by room type
        r = await client.get('/api/reception/rooms', params={'room_type': 'single'})
        single_rooms = r.json()['rooms']
        assert all(room['type'] == 'single' for room in single_rooms), "All rooms should be type 'single'"
        
        # Filter by cleanliness status
        r = await client.get('/api/reception/rooms', params={'cleanliness_status': 'Clean'})
        clean_rooms = r.json()['rooms']
        assert all(room['cleanliness_status'] == 'Clean' for room in clean_rooms), "All rooms should be Clean"
        
        # Filter by status (Occupied)
        r = await client.get('/api/reception/rooms', params={'status': 'Available'})
        available_rooms = r.json()['rooms']
        assert all(room['status'] == 'Available' for room in available_rooms), "All rooms should be Available"


@pytest.mark.asyncio
async def test_7_multiple_guests_checkout():
    """Test 7: Multiple guests can check in and check out independently"""
    setup_broker()
    from main import app
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        # Check in 3 guests
        guests = []
        for i in range(3):
            r = await client.post('/api/reception/checkin', params={'name': f'Guest {i+1}', 'room_number': i+1})
            assert r.status_code == 200
            guests.append(r.json()['guest'])
        
        # Verify rooms are occupied
        r = await client.get('/api/reception/rooms', params={'status': 'Occupied'})
        occupied = r.json()['rooms']
        assert len(occupied) == 3
        
        # Check out first guest
        r = await client.post('/api/reception/checkout', params={'guest_id': guests[0]['id']})
        assert r.status_code == 200
        bill = r.json()['bill']
        assert bill['guest_id'] == guests[0]['id']
        
        # Verify room is now Available and Dirty
        r = await client.get('/api/reception/rooms', params={'room_type': 'single'})
        rooms = r.json()['rooms']
        room1 = next(r for r in rooms if r['number'] == 1)
        assert room1['status'] == 'Available'
        assert room1['cleanliness_status'] == 'Dirty'
        
        # Verify other guests still occupied
        r = await client.get('/api/reception/rooms', params={'status': 'Occupied'})
        occupied = r.json()['rooms']
        assert len(occupied) == 2


@pytest.mark.asyncio
async def test_8_order_state_transitions():
    """Test 8: Room service orders can transition through valid states only"""
    setup_broker()
    from main import app
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        # Check in guest and place order
        r = await client.post('/api/reception/checkin', params={'name': 'Guest', 'room_number': 1})
        r = await client.post('/api/roomservice/order', params={'room_number': 1, 'items': 'Tea'})
        assert r.status_code == 200
        order_id = r.json()['id']
        
        # Transition to Preparing
        r = await client.post('/api/roomservice/update_state', params={'order_id': order_id, 'state': 'Preparing'})
        assert r.status_code == 200
        assert r.json()['state'] == 'Preparing'
        
        # Transition to Delivered
        r = await client.post('/api/roomservice/update_state', params={'order_id': order_id, 'state': 'Delivered'})
        assert r.status_code == 200
        assert r.json()['state'] == 'Delivered'
        
        # Invalid state should fail
        r = await client.post('/api/roomservice/update_state', params={'order_id': order_id, 'state': 'Invalid'})
        assert r.status_code == 400, "Invalid state should be rejected"
        
        # Nonexistent order
        r = await client.post('/api/roomservice/update_state', params={'order_id': '999', 'state': 'Preparing'})
        assert r.status_code == 200  # Returns error dict, not 404


@pytest.mark.asyncio
async def test_9_housekeeping_workflow():
    """Test 9: Complete housekeeping workflow (Dirty → Being cleaned → Clean)"""
    setup_broker()
    from main import app
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        # Check in and check out to make room Dirty
        r = await client.post('/api/reception/checkin', params={'name': 'Guest', 'room_number': 1})
        guest_id = r.json()['guest']['id']
        r = await client.post('/api/reception/checkout', params={'guest_id': guest_id})
        assert r.status_code == 200
        
        # Verify room is Dirty
        r = await client.get('/api/reception/rooms', params={'room_number': 1})
        room = r.json()['rooms'][0]
        assert room['cleanliness_status'] == 'Dirty'
        assert room['cleanliness_time'] is None
        
        # Start cleaning
        r = await client.post('/api/housekeeping/mark_cleaning', params={'room_number': 1})
        assert r.status_code == 200
        assert r.json()['status'] == 'Being cleaned'
        
        # Verify room status updated
        r = await client.get('/api/reception/rooms')
        room = next(r for r in r.json()['rooms'] if r['number'] == 1)
        assert room['cleanliness_status'] == 'Being cleaned'
        
        # Mark clean
        r = await client.post('/api/housekeeping/mark_clean', params={'room_number': 1})
        assert r.status_code == 200
        assert r.json()['status'] == 'Clean'
        
        # Verify cleanliness_time is set to today's date
        r = await client.get('/api/reception/rooms')
        room = next(r for r in r.json()['rooms'] if r['number'] == 1)
        assert room['cleanliness_status'] == 'Clean'
        assert room['cleanliness_time'] is not None  # Should have YYYY-MM-DD format


@pytest.mark.asyncio
async def test_10_maintenance_urgency_and_resolution():
    """Test 10: Maintenance issues can be reported and resolved with urgency levels"""
    setup_broker()
    from main import app
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        # Report multiple issues with different urgencies
        issues = []
        for urgency in [1, 3, 5]:
            r = await client.post('/api/maintenance/report', 
                                params={'room_number': 1, 'description': f'Issue urgency {urgency}', 'urgency': urgency})
            assert r.status_code == 200
            issues.append(r.json())
        
        # Get open issues
        r = await client.get('/api/maintenance/open')
        assert r.status_code == 200
        open_issues = r.json()['issues']
        assert len(open_issues) == 3
        assert all(issue['status'] == 'Open' for issue in open_issues)
        
        # Resolve first issue
        issue_id = issues[0]['id']
        r = await client.post('/api/maintenance/resolve', params={'issue_id': issue_id})
        assert r.status_code == 200
        assert r.json()['status'] == 'Resolved'
        
        # Verify open issues decreased
        r = await client.get('/api/maintenance/open')
        open_issues = r.json()['issues']
        assert len(open_issues) == 2, "Should have 2 open issues after resolving 1"
        assert all(issue['status'] == 'Open' for issue in open_issues)
        
        # Resolve remaining issues
        for issue in issues[1:]:
            r = await client.post('/api/maintenance/resolve', params={'issue_id': issue['id']})
            assert r.status_code == 200
        
        # Verify all resolved
        r = await client.get('/api/maintenance/open')
        open_issues = r.json()['issues']
        assert len(open_issues) == 0, "All issues should be resolved"