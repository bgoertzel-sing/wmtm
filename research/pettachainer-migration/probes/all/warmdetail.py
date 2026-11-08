import json,traceback
from goal_chainer.errors import ProtocolError
import tests.test_evidence_chainer as t
try:
    g=t.grading_group(budget=None); print("OK",g)
except ProtocolError as e:
    print("PERR",json.dumps(getattr(e,"details",None))[:2000])
except Exception as e:
    traceback.print_exc()
