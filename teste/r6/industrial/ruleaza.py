"""Runda 6 industrial — rulează frazele (r5 + r6) prin interpretor → constructor → validare → layout → SVG/PNG.
Rulare: python3 teste/r6/industrial/ruleaza.py r5|r6 [nr...]"""
import sys, json, pathlib, traceback
sys.path.insert(0, '/home/claude/sm')
from engine import interpretor, constructor, layout, render_svg, validare
D = pathlib.Path('/home/claude/sm/teste/r6/industrial')

def rezumat_model(m):
    out = []
    def ap(a):
        return f"{a.get('ref','')}:{a.get('tip')}[{' '.join(a.get('spec') or [])}]"
    def walk(o, ad=0):
        if isinstance(o, dict):
            if 'aparate' in o or 'sarcina' in o or 'sursa' in o:
                t = (o.get('sarcina') or {}).get('titlu') or (o.get('sursa') or {}).get('titlu') or o.get('titlu') or ''
                sub = (o.get('sarcina') or {}).get('sub') or (o.get('sursa') or {}).get('sub') or ''
                ca = (o.get('cablu') or {}).get('text', '') if isinstance(o.get('cablu'), dict) else ''
                out.append('  ' * ad + f"* {t} | {sub} | {' '.join(ap(a) for a in o.get('aparate') or [])} | {ca}")
            for k, v in o.items():
                if k in ('calc', 'cartus', 'calc_rezumat', 'materiale', 'note', 'legenda'): continue
                walk(v, ad + (1 if k in ('plecari', 'sub_plecari', 'copii', 'tablou') else 0))
        elif isinstance(o, list):
            for x in o: walk(x, ad)
    walk(m)
    c = m.get('carcasa') or {}
    out.insert(0, f"CARCASA {c.get('titlu')} | {c.get('sub')} | BARA {(m.get('bara') or {}).get('eticheta')} | lat: {[ap(a) for a in (m.get('bara') or {}).get('laterale') or []]}")
    return out

def ruleaza(fr, nr, tag, png=True):
    rec = dict(fr); rec['nr'] = nr
    try:
        r = interpretor.interpreteaza_local(fr['fraza'])
    except Exception as e:
        rec['eroare'] = 'interpretor: ' + traceback.format_exc()[-400:]; return rec
    rec.update(actiune=r.get('actiune'), tip=r.get('tip_schema'), refuz=r.get('refuz_cod'), refuz_motiv=r.get('refuz_motiv'),
               intrare=r.get('intrare_fizica'), intrebari=r.get('intrebari'), presupus=r.get('presupus'),
               avertismente=r.get('avertismente'), intelegere=r.get('intelegere'))
    if r.get('actiune') != 'refuza' and r.get('intrare_fizica'):
        try:
            m, rez = constructor.genereaza(r['intrare_fizica'])
            v = validare.valideaza(m)
            rec['blocheaza'] = v.get('blocheaza')
            rec['verif'] = [f"{x.get('cod')}/{x.get('nivel')}: {x.get('mesaj') or x.get('text') or ''}"[:220] for x in v.get('verificari') or [] if x.get('nivel') not in ('INFO', 'OK')]
            rec['model'] = rezumat_model(m)
            rec['note_plansa'] = m.get('note')
            if png:
                cv = layout.build(m); svg = render_svg.render(cv, f"{tag}{nr:02d}")
                (D / 'svg').mkdir(exist_ok=True); (D / 'png').mkdir(exist_ok=True)
                p = D / 'svg' / f"{tag}_{nr:02d}.svg"; p.write_text(svg, encoding='utf-8')
                import cairosvg
                cairosvg.svg2png(bytestring=svg.encode(), write_to=str(D / 'png' / f"{tag}_{nr:02d}.png"), output_width=2400)
        except Exception as e:
            rec['eroare'] = 'constructor/render: ' + traceback.format_exc()[-600:]
    return rec

if __name__ == '__main__':
    tag = sys.argv[1]
    sel = set(int(x) for x in sys.argv[2:])
    src = '/home/claude/sm/teste/r5/industrial/fraze.json' if tag == 'r5' else str(D / 'fraze_in.json')
    F = json.load(open(src))
    res = []
    for i, f in enumerate(F, 1):
        nr = f.get('nr', i)
        if sel and nr not in sel: continue
        fr = {'fraza': f['fraza'], 'asteptat': f['asteptat']}
        res.append(ruleaza(fr, nr, tag))
    out = D / (f'rezultat_{tag}.json')
    json.dump(res, open(out, 'w'), ensure_ascii=False, indent=1, default=str)
    for x in res:
        print(f"\n#{x['nr']} {x['fraza']}\n  ASTEPTAT: {x['asteptat']}\n  -> {x.get('actiune')} tip={x.get('tip')} refuz={x.get('refuz')} {x.get('refuz_motiv') or ''}")
        if x.get('eroare'): print('  EROARE', x['eroare'])
        if x.get('intrebari'): print('  INTREBARI', x['intrebari'])
        if x.get('intrare'): print('  IN', json.dumps(x['intrare'], ensure_ascii=False))
        if x.get('verif'): print('  VERIF blocheaza=', x.get('blocheaza'), x['verif'][:8])
        for l in x.get('model') or []: print('   ', l[:330])
