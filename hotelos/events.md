# Events (broker topics)

| Event Name | Publisher | Subscriber(s) | Payload |
|---|---|---|---|
| room_assigned | Reception Service | Dashboard, Housekeeping | {"guest": {...}, "room": {...}} |
| room_vacated | Reception Service | Housekeeping, Dashboard | {"room": {...}} |
| housekeeping_status | Housekeeping Service | Dashboard | {"room": room_number, "status": "Being cleaned"|"Clean"} |
| housekeeping_queue_updated | Housekeeping Service | Dashboard | {"room": room_number, "action": "enqueued"} |
| room_service_event | Room Service | Dashboard, Reception | {"order": {...}} |
| maintenance_reported | Maintenance Service | Dashboard, Maintenance team | {"issue": {...}} |
| maintenance_assigned | Maintenance Service | Dashboard | {"issue": {...}} |
| maintenance_resolved | Maintenance Service | Dashboard | {"issue": {...}} |
| billing_event | Reception Service | Billing (external)/Dashboard | {"guest_id": "...", "amount": 100.0} |

