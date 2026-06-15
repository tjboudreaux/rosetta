#!/usr/bin/env python3
"""Inference-time alias-aware retriever (NO pre-compilation). Builds an alias map from the corpus
glossary at query time, expands the query through aliases (token-overlap, both directions), greps history/.
Usage: python3 alias_search.py "<query>"
"""
import sys, re, glob
q=sys.argv[1] if len(sys.argv)>1 else ""
text="\n".join(open(f).read() for f in glob.glob("history/*.md"))
aliases={}
for m in re.finditer(r"'([^']+)'\s*(?:=|is)\s*([A-Za-z0-9 .()/-]+?)[.;]", text):
    aliases[m.group(1).strip().lower()]=re.sub(r'^(our|the|a)\s+','',m.group(2).strip(),flags=re.I)
for m in re.finditer(r"([A-Za-z -]+?) is internally '([^']+)'", text):
    aliases[re.sub(r'^the\s+','',m.group(1).strip(),flags=re.I).lower()]=m.group(2).strip()
def toks(s): return set(re.findall(r"[a-z0-9]+", s.lower()))
qt=toks(q); terms=set([q])
for k,v in aliases.items():
    if toks(k)&qt or toks(v)&qt: terms.add(k); terms.add(v)
# second hop: expand newly added terms once more
for k,v in aliases.items():
    if any(toks(k)&toks(t) or toks(v)&toks(t) for t in list(terms)): terms.add(k); terms.add(v)
print("ALIASES:", aliases)
print("EXPANDED TERMS:", sorted(t for t in terms if t))
print("---- matching history lines ----")
for line in text.splitlines():
    ll=line.lower()
    if any(t.lower() in ll for t in terms if len(t)>3):
        print(line)
