from fastapi import APIRouter, HTTPException, Query
import heapq
from typing import Dict, Any

from hotelos.broker import get_broker
import logging
logger = logging.getLogger('hotelos.maintenance')

_issue_id_counter = 0

router = APIRouter()

# priority queue: (priority, counter, issue)
_issues = []
_issue_counter = 0
issues_map: Dict[str, Dict[str, Any]] = {}

@router.post("/report")
async def report_issue(
    room_number: int = Query(..., gt=0, le=100),
    description: str = Query(..., min_length=5, max_length=256, strip_whitespace=True),
    urgency: int = Query(5, ge=1, le=5)
):
    global _issue_counter, _issue_id_counter
    _issue_id_counter += 1
    issue_id = str(_issue_id_counter)
    issue = {"id": issue_id, "room": room_number, "description": description, "urgency": urgency, "status": "Open"}
    heapq.heappush(_issues, (urgency, _issue_counter, issue_id))
    _issue_counter += 1
    issues_map[issue_id] = issue
    await get_broker().publish("maintenance_reported", {"issue": issue})
    logger.info('report_issue returning: %s', issue)
    return issue

@router.post("/resolve")
async def resolve_issue(
    issue_id: str = Query(..., min_length=1, strip_whitespace=True)
):
    issue = issues_map.get(issue_id)
    if not issue:
        return {"error": "not found"}
    issue["status"] = "Resolved"
    await get_broker().publish("maintenance_resolved", {"issue": issue})
    return issue

@router.get("/open")
async def open_issues():
    return {"issues": [v for v in issues_map.values() if v["status"] != "Resolved"]}
