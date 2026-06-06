from fastapi import APIRouter, HTTPException, Query
import asyncio
from typing import Dict, Any

from hotelos.broker import get_broker

router = APIRouter()

orders_queue: asyncio.Queue = asyncio.Queue()
orders: Dict[str, Dict[str, Any]] = {}
_order_id_counter = 0

@router.post("/order")
async def place_order(
    room_number: int = Query(..., gt=0, le=100),
    items: str = Query(..., min_length=1, max_length=256, strip_whitespace=True),
    amount: float | None = Query(None, ge=0.0)
):
    from hotelos.services import reception
    room = next((r for r in reception.rooms if r["number"] == room_number), None)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room["status"] != "Occupied":
        raise HTTPException(status_code=400, detail="Room service is only available for occupied rooms")

    global _order_id_counter
    _order_id_counter += 1
    order_id = str(_order_id_counter)
    order = {"id": order_id, "room": room_number, "items": items, "state": "Received", "amount": float(amount) if amount is not None else 10.0}
    orders[order_id] = order
    await orders_queue.put(order)
    await get_broker().publish("room_service_event", {"order": order})
    return order

@router.post("/update_state")
async def update_state(
    order_id: str = Query(..., min_length=1, strip_whitespace=True),
    state: str = Query(..., min_length=1, max_length=32, strip_whitespace=True)
):
    if state not in ("Received", "Preparing", "Delivered"):
        raise HTTPException(status_code=400, detail="Invalid order state")
    o = orders.get(order_id)
    if not o:
        return {"error": "order not found"}
    o["state"] = state
    await get_broker().publish("room_service_event", {"order": o})
    return o

@router.get("/orders")
async def list_orders():
    return {"orders": list(orders.values())}
