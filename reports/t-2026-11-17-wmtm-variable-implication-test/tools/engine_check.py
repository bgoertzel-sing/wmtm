
import sys,os
PETTA="/home/openclaw/research-agent/projects/omegaclaw/p1-engine/petta-3681b9b"; V="/home/openclaw/research-agent/projects/omegaclaw/p1-engine/pettachainer-bdae8d7e"
sys.path.insert(0,PETTA+"/python"); sys.path.insert(0,V); os.environ["PETTA_PATH"]=PETTA
from pettachainer.pettachainer import PeTTaChainer
for tv in ["(STV 1.0 0.9)", "(CTV (STV 1.0 0.9) (STV 0.0 0.001))"]:
    h=PeTTaChainer()
    [h.set_positive_only_predicate(c) for c in ("acoustic","quiet")]
    h.add_atom("(: imp (Implication (Member $x acoustic) (Member $x quiet)) %s)" % tv)
    h.add_atom("(: f1 (Member lute acoustic) (STV 1.0 0.9))")
    r=h.query("(: $prf (Member lute quiet) $tv)", steps=30, timeout_sec=0)
    print(tv, "->", r)
