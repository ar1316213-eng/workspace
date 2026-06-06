from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any
from datetime import datetime, timezone, timedelta

from hotelos.broker import get_broker

TZ_PLUS5 = timezone(timedelta(hours=5))
_guest_id_counter = 0

router = APIRouter()

# Data stores
# Add richer room metadata: floor, type, cleanliness status, cleanliness_time, proximity
room_types = ["single", "double", "suite", "accessible"]
proximities = ["elevator", "stairs", "none"]
rooms = []
for i in range(10):
    rooms.append({
        "number": i + 1,
        "status": "Available",
        "guest": None,
        "floor": 1 if (i < 5) else 2,
        "type": room_types[i % len(room_types)],
        "cleanliness_status": "Clean",
        "cleanliness_time": None,
        "proximity": proximities[i % len(proximities)],
    })
guests: Dict[str, Dict[str, Any]] = {}

# Simple room assignment algorithm: first available

def assign_room():
    for r in rooms:
        if r["status"] == "Available":
            return r
    return None

@router.post("/checkin")
async def checkin(
    name: str = Query(..., min_length=1, max_length=128, strip_whitespace=True),
    room_number: int = Query(..., gt=0, le=100)
):
    # Require explicit room selection for check-in
    room = next((r for r in rooms if r["number"] == room_number), None)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room["status"] != "Available":
        raise HTTPException(status_code=400, detail="Room not available")

    global _guest_id_counter
    _guest_id_counter += 1
    guest_id = str(_guest_id_counter)
    now_ts = datetime.now(tz=TZ_PLUS5).timestamp()
    guest = {"id": guest_id, "name": name, "room": room["number"], "checkin_time": now_ts}
    guests[guest_id] = guest
    room["status"] = "Occupied"
    room["guest"] = guest
    # publish room assignment event
    await get_broker().publish("room_assigned", {"guest": guest, "room": room})
    return {"guest": guest}

@router.post("/checkout")
async def checkout(
    guest_id: str = Query(..., min_length=1, strip_whitespace=True)
):
    guest = guests.get(guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    room_no = guest["room"]
    room = next((r for r in rooms if r["number"] == room_no), None)
    if not room:
        raise HTTPException(status_code=500, detail="Room not found")
    # Billing calculation: nights stayed + room service charges
    from hotelos.services import room_service
    now_ts = datetime.now(tz=TZ_PLUS5).timestamp()
    checkin_ts = guest.get("checkin_time") or now_ts
    seconds = max(0, now_ts - checkin_ts)
    import math
    nights = max(1, math.ceil(seconds / 86400))
    rates = {"single": 100.0, "double": 150.0, "suite": 300.0, "accessible": 120.0}
    room_type = room.get("type", "single")
    rate = rates.get(room_type, 100.0)
    room_charge = nights * rate
    service_charge = sum(o.get("amount", 0.0) for o in room_service.orders.values() if o.get("room") == room_no)
    total = room_charge + service_charge
    bill = {"guest_id": guest_id, "nights": nights, "room_rate": rate, "room_charge": room_charge, "service_charge": service_charge, "amount": total}
    # mark room vacated and dirty after checkout
    room["status"] = "Available"
    room["guest"] = None
    room["cleanliness_status"] = "Dirty"
    room["cleanliness_time"] = None
    # remove orders for this room
    room_service.orders = {oid: o for oid, o in room_service.orders.items() if o.get("room") != room_no}
    # publish events
    await get_broker().publish("billing_event", bill)
    await get_broker().publish("room_vacated", {"room": room})
    # remove guest record
    del guests[guest_id]
    return {"bill": bill}

@router.get("/rooms")
async def list_rooms(
    floor: int | None = Query(None, ge=1, le=100),
    room_type: str | None = Query(None, min_length=1),
    cleanliness_status: str | None = Query(None, min_length=1),
    proximity: str | None = Query(None, min_length=1),
    status: str | None = Query(None, min_length=1),
):
    filtered = rooms
    if floor is not None:
        filtered = [room for room in filtered if room["floor"] == floor]
    if room_type:
        filtered = [room for room in filtered if room["type"].lower() == room_type.lower()]
    if cleanliness_status:
        filtered = [room for room in filtered if room["cleanliness_status"].lower() == cleanliness_status.lower()]
    if proximity:
        filtered = [room for room in filtered if room["proximity"].lower() == proximity.lower()]
    if status:
        filtered = [room for room in filtered if room["status"].lower() == status.lower()]
    return {"rooms": filtered}

@router.get("/guest/{guest_id}")
async def get_guest(guest_id: str):
    g = guests.get(guest_id)
    if not g:
        raise HTTPException(status_code=404, detail="Guest not found")
    return g
