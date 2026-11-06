"""Classify each answer's proof kind from its PeTTaChainer proof term (no confidence threshold is used anywhere).
Kinds (Roman, Track P README "Roman's answers"):
  derivation            - rules applied to asserted facts only (rule-proof / by <rule> over sp*/i_* atoms)
  antecedent completion - the term contains an (inverted <rule> ...) node: a premise was estimated by running an
                          implication backwards from its consequent
  population prior      - the conclusion rests on a (prior ...) node with no asserted fact under it
Mixed terms report every kind present, in the order above. Stdlib only."""
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

def walk(t):
    yield t
    if isinstance(t, list):
        for c in t: yield from walk(c)

def has_fact(t):
    return any(isinstance(x, str) and re.fullmatch(r'sp\d+|i_\w+', x) for x in walk(t))

def kinds(proof):
    if not proof: return []
    t = parse(proof)
    body = t[1] if isinstance(t, list) and t and t[0] == ':' else t
    k = []
    nodes = [x for x in walk(body) if isinstance(x, list) and x]
    if any(n[0] in ('rule-proof', 'by', 'conjunction', 'merge/revision', 'conditioned') for n in nodes) and has_fact(body):
        k.append('derivation')
    if any(n[0] == 'inverted' for n in nodes): k.append('antecedent completion')
    # population prior: a (prior ...) node that is itself a premise of an inference step, i.e. not the cpu/likelihood
    # prior of an (inverted ...) or (reported ...) estimate and not the revision prior of a (factored-revision ...)
    CPU_PARENTS = ('inverted', 'reported', 'factored-revision')
    for n in nodes:
        if n[0] in CPU_PARENTS: continue
        if any(isinstance(c, list) and c and c[0] == 'prior' for c in n[1:]):
            k.append('population prior'); break
    return k

def rules_used(proof):
    if not proof: return []
    return sorted({n[1] for n in walk(parse(proof)) if isinstance(n, list) and len(n) > 1 and n[0] in ('by', 'rule-proof', 'inverted') and isinstance(n[1], str)})

if __name__ == '__main__':
    for path in sys.argv[1:]:
        r = json.loads(open(path).read().strip().splitlines()[-1])
        for q in r['queries']:
            print(json.dumps({'goal': q['goal'], 'ok': q['ok'], 'stv': q.get('stv'), 'kinds': kinds(q.get('proof')), 'rules': rules_used(q.get('proof'))}))
