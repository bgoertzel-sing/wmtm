#!/usr/bin/env python3
"""Downstream score for D runs with clerk-ab a1varload methods (narrow count rule, wide strict, reader /75, class-class Inheritance).
Verdict lookup = clerk-ab's (verdicts_unmatched, verdicts23 via B map, verdicts_new_varruns any run). Unjudged goals listed for new rulings.
Usage: dload_score.py EVID_DIR RUNS..."""
import json,csv,re,sys,os
E=sys.argv[1]; RUNS=sys.argv[2:]; C="/srv/hive-evidence/t-2026-11-18-wmtm-clerk-ab"; M="/srv/hive-evidence/t-2026-11-12-wmtm-parser-master-adopt-v2/armB"
R={"same_coref","coref_bearer","so_sym","coref_sym","between_sym"}
STRICT={"month_class","subset_is_part","partof_trans","becauseof_cause"}
d=json.load(open(M+"/full_s2/spec.json")); sc=json.load(open(M+"/full_s2/score.json"))
strip=lambda g: re.sub(r"__ep_note_\d+T\d+Z","",g)
bmap={}
for g,r in zip(d["goals"],sc["rows"]):
    m=re.search(r"ep_note_\d+T(\d+Z)",g); bmap[(m.group(1) if m else None,r["rule"],strip(g))]=r["goal_id"]
V23={r["goal"]:r["verdict"] for r in csv.DictReader(open(M+"/verdicts/verdicts23.tsv"),delimiter="\t")}
VU={(r["note"],r["rule"],r["goal"]):r["verdict"] for r in csv.DictReader(open(C+"/armload/verdicts_unmatched.tsv"),delimiter="\t")}
VN={(r["note"],r["rule"],r["goal"]):r["verdict"] for r in csv.DictReader(open(C+"/a1varload/verdicts_new_varruns.tsv"),delimiter="\t")}
VD={}
p=E+"/dload/verdicts_new_d.tsv"
if os.path.exists(p): VD={(r["note"],r["rule"],r["goal"]):r["verdict"] for r in csv.DictReader(open(p),delimiter="\t")}
RE=list(csv.DictReader(open(C+"/review3/refs/reader_expect.tsv"),delimiter="\t"))
want={(r["note"],r["rule"]) for r in RE if not r["rule"].startswith("GAP")}
def docs(path):
    D=[]
    for l in open(path):
        x=json.loads(l)
        if x["doc"] not in D: D.append(x["doc"])
    return [re.search(r"T(\d+Z)",n).group(1) for n in D]
def inh(p):
    tot=inst=cc=0; subs=set()
    for l in open(p):
        m=re.search(r"\(Inheritance (\S+) (\S+?)\)",json.loads(l)["atom"])
        if not m: continue
        tot+=1; s=m.group(1)
        if s.startswith("sk_") or re.match(r"t_\d{4}_",s): inst+=1
        else: cc+=1; subs.add((m.group(1),m.group(2)))
    return tot,inst,cc,subs
out={}; unj=set()
for run in RUNS:
    D=docs(f"{E}/{run}/run/parsed.jsonl"); seen=set(); wide=set(); c={"correct":0,"wrong":0,"uncertain":0,"UNJUDGED":0}; w={"correct":0,"wrong":0,"uncertain":0,"UNJUDGED":0}; nr=set()
    for l in open(f"{E}/dload/goals-{run}.jsonl"):
        x=json.loads(l); k=(D[x["doc"]],x["rule"],x["goal"]); nr.add((k[0],k[1]))
        if x["rule"] in R or k in seen: continue
        seen.add(k)
        v=VU.get(k) or V23.get(bmap.get(k,""),None) or VN.get(k) or VD.get(k) or "UNJUDGED"
        if v=="UNJUDGED": unj.add(k)
        c[v]+=1
        if x["rule"] in STRICT: w[v]+=1
    t,i,cc,subs=inh(f"{E}/dload/atoms-{run}.jsonl")
    hit=sorted(want&nr)
    out[run]={"docs":len(D),"narrow":{"n":len(seen),**c},"wide_strict":w,"reader":len(hit),"reader_of":len(want),"reader_hits":hit,
              "inheritance":t,"instance":i,"class_class":cc,"goals":sorted(map(list,seen)),"cc_pairs":sorted(map(list,subs))}
    print(run,"docs",len(D),"narrow",c,"wide",w,"reader",len(hit),"/",len(want),"inh",t,"inst",i,"cc",cc)
json.dump(out,open(E+"/dload/score/dload.json","w"),indent=1)
with open(E+"/dload/unjudged.tsv","w") as f:
    f.write("note\trule\tgoal\n")
    for k in sorted(unj): f.write("\t".join(k)+"\n")
print("unjudged distinct",len(unj))
