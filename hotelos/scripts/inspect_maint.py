import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import inspect
from hotelos.services import maintenance

print('report_issue object:', maintenance.report_issue)
print('callable:', callable(maintenance.report_issue))
print('name:', getattr(maintenance.report_issue, '__name__', None))
print('repr:', repr(maintenance.report_issue))
try:
    src = inspect.getsource(maintenance.report_issue)
    print('source:\n', src)
except Exception as e:
    print('could not get source:', e)
