from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Query
import asyncio
from typing import Dict, Any

from hotelos.broker import get_broker

TZ_PLUS5 = timezone(timedelta(hours=5))

router = APIRouter()

cleaning_queue: asyncio.Queue = asyncio.Queue()
rooms_status: Dict[int, str] = {i: "Available" for i in range(1, 11)}

@router.post("/mark_cleaning")
async def mark_cleaning(
    room_number: int = Query(..., gt=0, le=100)
):
    from hotelos.services import reception

    room = next((r for r in reception.rooms if r["number"] == room_number), None)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    room["cleanliness_status"] = "Being cleaned"
    room["cleanliness_time"] = None
    rooms_status[room_number] = "Being cleaned"
    await get_broker().publish("housekeeping_status", {"room": room_number, "status": "Being cleaned"})
    return {"room": room_number, "status": rooms_status[room_number]}

@router.post("/mark_clean")
async def mark_clean(
    room_number: int = Query(..., gt=0, le=100)
):
    from hotelos.services import reception

    room = next((r for r in reception.rooms if r["number"] == room_number), None)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    room["cleanliness_status"] = "Clean"
    room["cleanliness_time"] = datetime.now(tz=TZ_PLUS5).strftime('%Y-%m-%d')
    rooms_status[room_number] = "Clean"
    await get_broker().publish("housekeeping_status", {"room": room_number, "status": "Clean"})
    return {"room": room_number, "status": rooms_status[room_number]}

# HTTP endpoint to view queue length
@router.get("/queue")
async def queue_len():
    return {"queue": cleaning_queue.qsize()}

# technicians/housekeepers can pop from queue via an endpoint
@router.post("/next")
async def next_room():
    if cleaning_queue.empty():
        return {"room": None}
    room = await cleaning_queue.get()
    rooms_status[room] = "Being cleaned"
    await get_broker().publish("housekeeping_status", {"room": room, "status": "Being cleaned"})
    return {"room": room}
