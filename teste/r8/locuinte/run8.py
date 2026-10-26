import sys, json, traceback
sys.path.insert(0, '/home/claude/sm')
from engine import interpretor, constructor, layout, render_svg, validare
import cairosvg
D = '/home/claude/sm/teste/r8/locuinte'
F = json.load(open(D + '/fraze.json'))
only = set(int(x) for x in sys.argv[1:])
out = []

def ap_s(a):
    s = a.get('ref', '') + ':' + a.get('tip', '')
    if a.get('spec'): s += '[' + ' | '.join(a['spec']) + ']'
    elif a.get('param'):
        s += '[' + ','.join(f"{k}={v}" for k, v in a['param'].items() if k in ('In_A','poli','IdN_mA','tip_ddr','curba')) + ']'
    return s

def plec(p, ind='  '):
    L = []
    t = (p.get('sarcina') or {}).get('titlu') or p.get('nume') or p.get('titlu')
    sub = (p.get('sarcina') or {}).get('sub', '')
    L.append(f"{ind}- {t} ({sub}) :: " + ' ; '.join(ap_s(a) for a in p.get('aparate', [])) + ' :: ' + str((p.get('cablu') or {}).get('text', '')))
    for k in ('copii', 'plecari', 'circuite'):
        for c in p.get(k) or []:
            if isinstance(c, dict): L += plec(c, ind + '    ')
    if p.get('tablou'):
        for c in (p['tablou'].get('plecari') or []): L += plec(c, ind + '    ')
    return L

for f in F:
    if only and f['id'] not in only: continue
    rec = {'id': f['id'], 'text': f['text']}
    try:
        r = interpretor.interpreteaza_local(f['text'])
        rec.update({k: r.get(k) for k in ('actiune', 'tip_schema', 'intrebari', 'neconsumat', 'presupus', 'avertismente', 'refuz_cod', 'refuz_motiv', 'intrare_fizica', 'intelegere', 'motor')})
        if r.get('actiune') != 'refuza' and r.get('intrare_fizica'):
            m, rez = constructor.genereaza(r['intrare_fizica'])
            v = validare.valideaza(m)
            rec['verificari'] = [f"{x['nivel']} {x['cod']} {x.get('obiect','')}: {x.get('mesaj','')[:160]}" for x in v['verificari']]
            rec['blocheaza'] = v['blocheaza']
            rec['titlu'] = m['cartus'].get('denumire2')
            L = []
            for i in m.get('intrari', []):
                L.append('INTRARE ' + str((i.get('sursa') or {})) + ' C1=' + str((i.get('cablu') or {}).get('text')) + ' C2=' + str((i.get('cablu_ca') or {}).get('text')))
                L.append('  ' + ' ; '.join(ap_s(a) for a in i.get('aparate', []) if a.get('tip') != 'nod'))
            b = m.get('bara') or {}
            L.append('BARA ' + str(b.get('eticheta')) + ' lat=' + ' ; '.join(ap_s(a) for a in b.get('laterale', [])))
            for p in m.get('plecari', []): L += plec(p)
            rec['model'] = L
            rec['note'] = m.get('note')
            cv = layout.build(m); svg = render_svg.render(cv, 't')
            cairosvg.svg2png(bytestring=svg.encode(), write_to=f"{D}/f{f['id']:02d}.png", output_width=2400)
            rec['png'] = f"f{f['id']:02d}.png"
    except Exception as e:
        rec['exceptie'] = traceback.format_exc()[-800:]
    out.append(rec)
    print(f"#{f['id']} {f['text']}\n  -> {rec.get('actiune')} / {rec.get('tip_schema')} blocheaza={rec.get('blocheaza')}")
    print('  intr:', json.dumps(rec.get('intrare_fizica'), ensure_ascii=False)[:900])
    print('  INT:', (rec.get('intelegere') or '')[:500].replace(chr(10),' / ')); print('  Q:', rec.get('intrebari')); print('  nec:', rec.get('neconsumat'))
    print('  pres:', rec.get('presupus')); print('  avert:', rec.get('avertismente'))
    if rec.get('exceptie'): print('  EXC', rec['exceptie'])
    for l in rec.get('model', []): print('   ', l[:400])
    for l in rec.get('verificari', []): print('   V', l[:220])
    print()
json.dump(out, open(D + '/rezultate' + ('_part' if only else '') + '.json', 'w'), ensure_ascii=False, indent=1, default=str)
