import json,sys
R=json.load(open('rezultate.json'))
lo=int(sys.argv[1]); hi=int(sys.argv[2])
for r in R:
    if not lo<=r['id']<=hi: continue
    i=r.get('intrare_fizica') or {}
    ii={k:v for k,v in i.items() if k!='circuite'}
    circ=[(c.get('nume'),c.get('P_kW'),c.get('faza'),c.get('In_A')) for c in i.get('circuite',[])]
    print(f"#{r['id']} {r['text'][:300]!r}\n -> {r.get('actiune')}/{r.get('tip_schema')} bloc={r.get('blocheaza')}")
    print('  in:',json.dumps(ii,ensure_ascii=False)[:600]); 
    if circ: print('  circ:',circ)
    print('  INT:',(r.get('intelegere') or '').split('\n')[0][:300])
    print('  Q:',r.get('intrebari')); print('  nec:',r.get('neconsumat'))
    print('  avert:',r.get('avertismente'))
    if r.get('exceptie'): print('  EXC',r['exceptie'][-300:])
    for l in r.get('model',[])[:int(sys.argv[3]) if len(sys.argv)>3 else 16]: print('   ',l[:260])
    for l in r.get('verificari',[]): 
        if 'BLOCANT' in l or 'V4' in l or 'V3' in l or 'V0' in l: print('   V',l[:200])
    print()
