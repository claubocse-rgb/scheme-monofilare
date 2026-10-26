import sys, json, traceback
sys.path.insert(0,'/home/claude/sm')
from engine import interpretor, constructor, layout, render_svg, validare
import cairosvg
D='/home/claude/sm/teste/r7/industrial/'
F=json.load(open(D+'fraze.json'))
only=set(int(a) for a in sys.argv[1:])
KEYS=('spec','text','titlu','sub','eticheta')
def flat(o,p,out):
    if isinstance(o,dict):
        for k,v in o.items():
            if k in ('calc','cartus','materiale','legenda','calc_rezumat','param','lista'): continue
            flat(v,p+'.'+k,out)
    elif isinstance(o,list):
        for i,v in enumerate(o): flat(v,p+'[%d]'%i,out)
    else:
        k=p.rsplit('.',1)[-1].split('[')[0]
        if k in KEYS and o not in ('',None): out.append(f"{p}: {o}")
res={}
for f in F:
    if only and f['id'] not in only: continue
    r={'id':f['id']}
    try:
        it=interpretor.interpreteaza(f['text'])
        for k in ('actiune','tip_schema','presupus','intrebari','avertismente','refuz_cod','refuz_motiv','intrare_fizica'):
            r[k]=it.get(k)
        if it.get('actiune')!='refuza' and it.get('intrare_fizica'):
            m,rez=constructor.genereaza(it['intrare_fizica'])
            r['validare']=validare.valideaza(m)
            out=[]; flat(m,'',out); r['model']=out
            r['note']=m.get('note'); r['lista_pe']=m.get('lista_pe')
            cv=layout.build(m); svg=render_svg.render(cv,'t')
            open(D+'p%02d.svg'%f['id'],'w').write(svg)
            cairosvg.svg2png(bytestring=svg.encode(),write_to=D+'p%02d.png'%f['id'],output_width=2400)
    except Exception as e:
        r['exc']=traceback.format_exc()[-800:]
    res[f['id']]=r
json.dump(res,open('/home/claude/sm/teste/r7/industrial/res.json','w'),ensure_ascii=False,indent=1,default=str)
for f in F:
    if f['id'] not in res: continue
    r=res[f['id']]
    print('='*100); print('#%d'%f['id'], repr(f['text'])); print('EXP:',f['asteptat'])
    print('ACT:',r.get('actiune'),'| TIP:',r.get('tip_schema'),'| REFUZ:',r.get('refuz_cod'),r.get('refuz_motiv'))
    if r.get('exc'): print('EXC',r['exc'])
    print('INTR:',json.dumps(r.get('intrare_fizica'),ensure_ascii=False))
    for q in r.get('intrebari') or []: print('  Q:',q)
    for q in r.get('avertismente') or []: print('  W:',q)
    for q in r.get('presupus') or []: print('  P:',q[:160])
    v=r.get('validare')
    if v: print('  VAL:',json.dumps(v,ensure_ascii=False)[:600])
    for l in r.get('model') or []: print('   M',l[:170])
    if r.get('note'): print('  NOTE:',json.dumps(r['note'],ensure_ascii=False)[:900])
