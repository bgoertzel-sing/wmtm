import json,statistics as S
rows={}
for tag in ('before','after'):
  A=[];B=[];Am=[];Bm=[]
  for i in range(1,6):
    d=json.load(open(f'bench_{tag}_run{i}.json'))
    A.append(d['part_a_s12_3']['recall_s_mean']*1e6); B.append(d['part_b_scale']['recall_s_mean']*1e3)
    Am.append(d['part_a_s12_3']['recall_s_median']*1e6); Bm.append(d['part_b_scale']['recall_s_median']*1e3)
    last=d
  a=last['part_a_s12_3']; b=last['part_b_scale']
  rows[tag]=dict(A_mean_us_runs=[round(x,1) for x in A],A_median_of_run_medians_us=round(S.median(Am),1),B_mean_ms_runs=[round(x,1) for x in B],B_median_of_run_medians_ms=round(S.median(Bm),1),
    A_candidates_max=a['candidates_max'],A_candidates_mean=a['candidates_mean'],A_graph_only_mean=a['graph_only_candidates_mean'],A_graph_only_max=a['graph_only_candidates_max'],A_occupancy_max=a['occupancy_max'],A_useful_resident_end=a['useful_resident_end'],
    B_candidates_max=b['candidates_max'],B_graph_only_mean=b['graph_only_candidates_mean'])
json.dump(rows,open('bench_summary.json','w'),indent=1)
print(json.dumps(rows,indent=1))