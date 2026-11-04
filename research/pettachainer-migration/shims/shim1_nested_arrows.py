# Shim 1 (scratch only): pymetta refuses annotated arrows whose parameter/output types are
# themselves annotated arrows ("nested products are not enforced"). Keep the outer -[c]->,
# rewrite nested -[c]-> to plain -> inside each (: name TYPE) declaration.
import re, sys, pathlib
root = pathlib.Path(sys.argv[1]); changed = 0; files = 0
def decl_spans(s):
    i = 0
    while True:
        i = s.find("(: ", i)
        if i < 0: return
        d = 0; j = i
        while j < len(s):
            if s[j] == "(": d += 1
            elif s[j] == ")":
                d -= 1
                if d == 0: break
            j += 1
        yield i, j + 1; i = j + 1
for p in sorted(root.rglob("*.metta")):
    s = p.read_text(); out = []; last = 0; n = 0
    for a, b in decl_spans(s):
        seg = s[a:b]; ms = list(re.finditer(r"-\[[^]]+\]->", seg))
        if len(ms) > 1:
            first = ms[0].end()
            new = seg[:first] + re.sub(r"-\[[^]]+\]->", "->", seg[first:])
            n += len(ms) - 1; out.append(s[last:a]); out.append(new); last = b
    if n:
        out.append(s[last:]); p.write_text("".join(out)); changed += n; files += 1
        print(f"{p.relative_to(root)}: {n}")
print("TOTAL nested arrows rewritten:", changed, "in", files, "files")
