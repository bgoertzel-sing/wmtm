"""Proof makeup per answer: walk EVERY node of each PeTTaChainer proof term (not only the top-level step).
Constructors at PeTTaChainer bdae8d7e:
  derivation            (by <rule> ...)                          plans.metta:19, compiler/rules.metta:265
  antecedent completion (antecedent-completion ...), (inverted ..) compiler/rules.metta:572/418, LANGUAGE_SPEC.md:913/624
  population prior      (population-prior ...)                   runtime/backward/skeleton.metta:1155
A (prior ..) under inverted/antecedent-completion/reported/factored-revision is the step's own cpu/revision prior, not a
population-prior proof, and is not counted.  Makeup: 'derivation only', 'partly' (derivation plus completion/prior),
'wholly' (completion/prior with no derivation step).  'top' = kind of the outermost step only (the old rule).
Stdlib only; reads the saved shadow runs, no rerun."""
import json, re, sys
def parse(s):
    toks = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', s)
    def rd(i):
        if toks[i] == '(':
            out = []; i += 1
            while toks[i] != ')':
                x, i = rd(i); out.append(x)
            return out, i + 1
        return toks[i], i + 1
    return rd(0)[0]
def nodes(t):
    if isinstance(t, list):
        yield t
        for c in t: yield from nodes(c)
def head(n):
    h = n[0] if n else None
    while isinstance(h, list) and h: h = h[0]      # ((inverted r with cpu P) w) -> inverted
    return h
KIND = {'by': 'derivation', 'rule-proof': 'derivation', 'inverted': 'antecedent completion',
        'antecedent-completion': 'antecedent completion', 'population-prior': 'population prior'}
def analyse(proof):
    if not proof: return None
    t = parse(proof); body = t[1] if isinstance(t, list) and t and t[0] == ':' else t
    counts = {}
    for n in nodes(body):
        k = KIND.get(n[0]) if isinstance(n[0], str) else None
        if k: counts[k] = counts.get(k, 0) + 1
    hb = head(body) if isinstance(body, list) else None
    top = KIND.get(hb, 'asserted fact' if isinstance(body, str) else str(hb))
    d = counts.get('derivation', 0); o = sum(v for k, v in counts.items() if k != 'derivation')
    makeup = 'derivation only' if d and not o else 'partly' if d and o else 'wholly' if o else 'asserted only'
    return {'kinds': sorted(counts), 'counts': counts, 'top': top, 'makeup': makeup}
if __name__ == '__main__':
    for path in sys.argv[1:]:
        for q in json.loads(open(path).read().strip().splitlines()[-1])['queries']:
            print(json.dumps({'run': path, 'goal': q['goal'], 'ok': q.get('ok'), 'stv': q.get('stv'), **(analyse(q.get('proof')) or {'makeup': 'no proof'})}))
