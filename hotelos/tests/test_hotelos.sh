#!/bin/bash
# HotelOS Comprehensive Test Script
# Run this after starting Redis + all 4 services

echo "Starting HotelOS Test Suite..."
echo "========================================"

BASE_URL="http://localhost:8001"  # Reception
echo "Testing Reception Service..."

# Test 1: Check-in with specific room
echo -e "\n1. TS-01: Guest Check-in"
curl -s -X POST "$BASE_URL/api/reception/checkin?name=Alice%20Smith&room_number=101" | jq

# Test 2: Another check-in
echo -e "\n2. TS-06: Second simultaneous-style check-in"
curl -s -X POST "$BASE_URL/api/reception/checkin?name=Bob%20Johnson&room_number=202" | jq

# Test 3: Room Service Order
echo -e "\n3. TS-04: Place Room Service Order"
curl -s -X POST "http://localhost:8003/api/roomservice/order?room_number=101&items=Coffee%2C%20Sandwich&amount=28.5" | jq

# Test 4: Update Order State
echo -e "\n4. Update Order State (Preparing)"
curl -s -X POST "http://localhost:8003/api/roomservice/update_state?order_id=1&state=Preparing" | jq

# Test 5: Maintenance Issue (Critical)
echo -e "\n5. TS-05: Report Critical Maintenance"
curl -s -X POST "http://localhost:8004/api/maintenance/report?room_number=103&description=Broken%20air%20conditioner&urgency=1" | jq

# Test 6: Housekeeping - Start Cleaning
echo -e "\n6. Housekeeping: Mark room as Being Cleaned"
curl -s -X POST "http://localhost:8002/api/housekeeping/mark_cleaning?room_number=202" | jq

# Test 7: Housekeeping - Mark Clean
echo -e "\n7. TS-03: Mark Room as Clean"
curl -s -X POST "http://localhost:8002/api/housekeeping/mark_clean?room_number=202" | jq

# Test 8: Checkout + Billing (Zero extra charges test)
echo -e "\n8. TS-02 & TS-10: Checkout with Billing"
curl -s -X POST "$BASE_URL/api/reception/checkout?guest_id=1" | jq

# Test 9: List Rooms (with filters)
echo -e "\n9. List Rooms with Filters"
curl -s "$BASE_URL/api/reception/rooms?floor=1&cleanliness_status=Clean" | jq

# Test 10: Invalid Input (Validation)
echo -e "\n10. TS-08: Invalid Input Test"
curl -s -X POST "$BASE_URL/api/reception/checkin?name=&room_number=999" | jq

echo -e "\n All tests completed!"
echo "Open the dashboard (dashboard/index.html) to verify real-time updates."