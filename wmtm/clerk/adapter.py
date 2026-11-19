"""Clerk landing -> PeTTaChainer-master atoms, using only the fixed vocab_map (ea11c90/1842a69).
t-2026-11-18-wmtm-clerk-ab, review-2 finding 1. No note text is stored here; callers keep counts.

translate(landings, doc) -> (atoms, unmapped)
  atoms:    list of "(: name TERM (STV s c))" strings, one per loaded unit
  unmapped: list of (reason, head) pairs, one per landing NOT loaded (retention set, counts only)
Rules, all from vocab_map:
  - top-level (and ...) is split into its conjuncts; PEELED wrappers are removed
  - (exists (vars) body) outside an antecedent -> skolems sk_<class>_<n>, body conjuncts loaded
  - (forall (vars) (implies A B)) and bare (implies A B) -> Implication, vars kept as $x<n>;
    exists inside the antecedent -> $var
  - one-arg (K x): Member if x is an individual/skolem id, else Inheritance (x K); COPULA heads likewise
  - called -> Name, equal/same-as/identity -> Similarity, not -> Not, in-context -> Context
  - any other head with >= 2 args -> (Evaluation head (List args))
  - a landing that contains an UNMAPPED head, 'most', or a one-arg head over a compound is not loaded
"""
import re
from . import vocab_map as V

FACT_TV = "(STV 1.0 0.99)"
RULE_TV = "(STV 0.9 0.7)"   # same truth A1's lowering gives parser implications


class Unmapped(Exception):
    pass


def tok(s):
    return re.findall(r'\(|\)|"[^"]*"|[^\s()]+', s)


def parse(s):
    t = tok(s); i = 0
    def rd():
        nonlocal i
        x = t[i]; i += 1
        if x == '(':
            l = []
            while t[i] != ')':
                l.append(rd())
            i += 1
            return l
        return x
    return rd()


def render(x):
    return '(' + ' '.join(map(render, x)) + ')' if isinstance(x, list) else x


def sym(s):
    if s.startswith('"') or s.startswith('$'):
        return s
    return re.sub(r'[^A-Za-z0-9_]', '_', s)


class _Doc:
    def __init__(self, doc):
        self.doc = doc; self.n = 0; self.sk = {}

    def skolem(self, cls):
        self.n += 1
        return f"sk_{sym(cls or 'e')}_{self.n}"


def _is_ind(x, env, raw=None):
    """Individual test on the RAW Clerk symbol (manual v10.3 s.3: name/kind word + number), before
    sym() turns '-' into '_'; skolems and bound variables are individuals too."""
    if isinstance(raw, str) and (V.is_individual(raw) or V.is_skolem(raw)):
        return True
    return isinstance(x, str) and (x.startswith('$') or (x.startswith('sk_') and x in env.values()))


def _cls_of(var, body):
    for c in (body[1:] if isinstance(body, list) and body and body[0] == 'and' else [body]):
        if isinstance(c, list) and len(c) == 2 and c[1] == var and isinstance(c[0], str):
            return c[0]
    return None


def _term(x, env, d, rule):
    """Translate one formula/argument to a wmtm term."""
    if isinstance(x, str):
        if x.startswith('$'):
            if x not in env:
                raise Unmapped('free-var')
            return env[x]
        return sym(x)
    if not x:
        raise Unmapped('empty')
    h = x[0]
    if not isinstance(h, str):
        raise Unmapped('compound-head')
    a = x[1:]
    if h in V.UNMAPPED or h == 'most':
        raise Unmapped(h)
    if h in V.PEELED:
        return _term(a[-1], env, d, rule)
    if h == 'exists':
        env2 = dict(env)
        for v in a[0]:
            env2[v] = f"$x{len(env2)+1}" if rule else d.skolem(_cls_of(v, a[1]))
        return _term(a[1], env2, d, rule)
    if h == 'forall':
        env2 = dict(env)
        for v in a[0]:
            env2[v] = f"$x{len(env2)+1}"
        return _term(a[1], env2, d, True)
    if h in V.RULE:
        return [V.RULE[h], _term(a[0], env, d, True), _term(a[1], env, d, rule)]
    if h in V.CONNECTIVE:
        args = [_term(y, env, d, rule) for y in a]
        if h == 'and' and len(args) == 1:
            return args[0]
        return [V.CONNECTIVE[h]] + args
    if h in V.CONTEXT:
        return [V.CONTEXT[h]] + [_term(y, env, d, rule) for y in a]
    if h in V.NAME and len(a) == 2:
        return [V.NAME[h], _arg(a[0], env, d, rule), _arg(a[1], env, d, rule)]
    if h in V.IDENTITY and len(a) == 2:
        return [V.IDENTITY[h], _arg(a[0], env, d, rule), _arg(a[1], env, d, rule)]
    if h in V.COPULA and len(a) == 2:
        s = _term(a[0], env, d, rule); k = _term(a[1], env, d, rule)
        ind = _is_ind(s, env, a[0])
        return [V.COPULA[h][0] if ind else V.COPULA[h][1], s, k]
    if len(a) == 1:
        if isinstance(a[0], list):
            raise Unmapped('one-arg-compound:' + h)
        s = _term(a[0], env, d, rule)
        ind = _is_ind(s, env, a[0])
        return [V.ONE_ARG[0] if ind else V.ONE_ARG[1], s, sym(h)]
    if len(a) == 0:
        raise Unmapped('zero-arg')
    return [V.DEFAULT, sym(h), ['List'] + [_arg(y, env, d, rule) for y in a]]


def _arg(x, env, d, rule):
    """An argument position holds a term: variables/symbols map as usual, a nested application
    stays a plain term (h a ...) so no Member/Inheritance/Evaluation is asserted from inside it."""
    if isinstance(x, str):
        return _term(x, env, d, rule)
    if not x or not isinstance(x[0], str):
        raise Unmapped('compound-head')
    if x[0] in V.UNMAPPED or x[0] in ('most', 'exists', 'forall'):
        raise Unmapped('arg:' + x[0])
    return [sym(x[0])] + [_arg(y, env, d, rule) for y in x[1:]]


def _units(x):
    """Split top-level and / exists-with-and into separately loaded units (skolems shared)."""
    if isinstance(x, list) and x and x[0] in V.PEELED:
        return _units(x[-1])
    if isinstance(x, list) and x and x[0] == 'and':
        return [u for y in x[1:] for u in _units(y)]
    return [x]


def translate(landings, doc):
    d = _Doc(doc); atoms = []; unmapped = []; k = 0
    for li, s in enumerate(landings):
        try:
            x = parse(s)
            if isinstance(x, list) and x and x[0] == 'exists':
                env = {}
                for v in x[1]:
                    env[v] = d.skolem(_cls_of(v, x[2]))
                terms = [_term(u, env, d, False) for u in _units(x[2])]
            else:
                terms = [_term(u, {}, d, False) for u in _units(x)]
        except Unmapped as e:
            unmapped.append((str(e), s.lstrip('(').split()[0] if s else '')); continue
        except (IndexError, ValueError):
            unmapped.append(('malformed', '')); continue
        for t in terms:
            k += 1
            tv = RULE_TV if t[0] == 'Implication' else FACT_TV
            atoms.append(f"(: b_l{li}_{k} {render(t)} {tv})")
    return atoms, unmapped
