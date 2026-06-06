import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import asyncio
from hotelos.broker import InMemoryBroker, set_broker_instance
set_broker_instance(InMemoryBroker())
from hotelos.services import maintenance

async def run():
    res = await maintenance.report_issue(1, 'Light out', 1)
    print('direct call result:', res)

asyncio.run(run())
