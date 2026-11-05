# PC3 numeric check: posterior of A, B and (And A B) given a stored (And A B) STV 1.0/0.99,
# uniform Beta(1,1) priors on A and B, Pearl factor m = (n*s+1)/(n+2), n = K*c/(1-c), K=800.
# Prints: grid posterior mean/var/conf, the event_node.pl polynomial_answer ratio bound, and a Z>=1-m bound.
import math
from fractions import Fraction as F
import numpy as np
K=800; s,c=F(1),F(99,100); n=K*c/(1-c); m=(n*s+1)/(n+2)
def conf(V,S):
    if V>=S*(1-S): return 0.0
    nn=S*(1-S)/V-1; return nn/(nn+K)
g=np.linspace(0,1,4001)[1:-1]; A,B=np.meshgrid(g,g); mf=float(m)
Z=A*B*mf+(1-A*B)*(1-mf)
E={0:F(1),1:F(1,2),2:F(1,3)}
def Ep(p): return sum(cf*E[i]*E[j] for (i,j),cf in p.items())
def mul(p,q):
    r={}
    for (a,b),x in p.items():
        for (c_,d_),y in q.items():
            k=(a+c_,b+d_); r[k]=r.get(k,0)+x*y
    return r
Zp={(0,0):1-m,(1,1):2*m-1}
for name,Ng,Np in [("A",A*B*mf+A*(1-B)*(1-mf),{(1,0):1-m,(1,1):2*m-1}),("And",A*B*mf,{(1,1):m})]:
    w=Z/Z.sum(); p=Ng/Z; S=float((w*p).sum()); V=float((w*(p-S)**2).sum())
    EZ=Ep(Zp); ZVar=Ep(mul(Zp,Zp))-EZ**2; EN=Ep(Np); Ce=EN/EZ
    Q=Ep(mul(Np,Np))-2*Ce*Ep(mul(Np,Zp))+Ce*Ce*Ep(mul(Zp,Zp)); b=max(Ce,1-Ce)
    bound=(float(Q)+float(b)*math.sqrt(float(ZVar*Q)))/float(EZ)**2
    zmin=float(Q)/float(1-m)/float(EZ); Mx=float(Ce*(1-Ce))
    print(f"{name}: mean={float(Ce):.10f} s(1-s)={Mx:.3e} engine_bound={bound:.3e} (c={conf(bound,float(Ce)):.2g}) "
          f"Zmin_bound={zmin:.3e} (c={conf(zmin,float(Ce)):.2g}) grid_var={V:.3e} (c={conf(V,S):.2f})")
