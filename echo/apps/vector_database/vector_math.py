from __future__ import annotations
import math

def cosine_similarity(left,right):
    if len(left)!=len(right) or not left: return 0.0
    dot=sum(float(a)*float(b) for a,b in zip(left,right)); ln=math.sqrt(sum(float(a)**2 for a in left)); rn=math.sqrt(sum(float(b)**2 for b in right))
    return dot/(ln*rn) if ln and rn else 0.0

def rank(query_vector,candidates):
    return sorted(((cosine_similarity(query_vector,vector),identifier) for identifier,vector in candidates),reverse=True)
