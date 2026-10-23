/* Versiunea web: motorul Python al aplicației rulează în acest worker, prin Pyodide (CPython compilat în WebAssembly). */
// fișierele .whl / .zip sunt publicate cu sufixul .wasm (tip servit de gazdă); cererile le primesc transparent
const _f = self.fetch.bind(self);
self.fetch = (u, o) => { const s = String(u && u.url || u); return _f(/\.(whl|zip)$/.test(s) ? s + '.wasm' : u, o); };
importScripts('pyodide/pyodide.js');

// bibliotecile grele se încarcă abia la primul export care le cere (pornirea rămâne mică: doar Python + motorul)
const LIB_DXF = ['pyodide/numpy-1.26.4-cp312-cp312-pyodide_2024_0_wasm32.whl', 'whl/typing_extensions-4.16.0-py3-none-any.whl',
  'whl/pyparsing-3.3.3-py3-none-any.whl', 'whl/fonttools-4.67.0-py3-none-any.whl', 'whl/ezdxf-1.4.5-py3-none-any.whl'];
const LIB_XLSX = ['whl/et_xmlfile-2.0.0-py3-none-any.whl', 'whl/openpyxl-3.1.5-py2.py3-none-any.whl'];
const NEVOI = { '/api/export/dxf': [LIB_DXF], '/api/export/xlsx': [LIB_XLSX], '/api/export/deviz': [LIB_XLSX],
  '/api/preturi/import': [LIB_XLSX], '/api/export/pachet': [LIB_DXF, LIB_XLSX] };
let api = null, bootP = null, PY = null, BASE = '';
const incarcate = new Map();
function asigura(lib, tacut) {
  if (!incarcate.has(lib)) incarcate.set(lib, (async () => {
    if (!tacut) progres(lib === LIB_DXF ? 'Încarc biblioteca DXF (o singură dată)…' : 'Încarc biblioteca Excel (o singură dată)…');
    await PY.loadPackage(lib.map(f => BASE + f));
  })());
  return incarcate.get(lib);
}
const progres = text => postMessage({ tip: 'progres', text });

async function boot(date) {
  const base = new URL('.', self.location.href).href;
  progres('Pornesc Python în browser…');
  const py = await loadPyodide({ indexURL: base + 'pyodide/' });
  PY = py; BASE = base;
  progres('Încarc motorul de calcul…');
  const src = await (await _f(base + 'app_src.json')).json();
  for (const [p, txt] of Object.entries(src)) {
    const full = '/app/' + p; py.FS.mkdirTree(full.slice(0, full.lastIndexOf('/'))); py.FS.writeFile(full, txt);
  }
  py.runPython('import sys; sys.path.insert(0, "/app"); sys.path.insert(0, "/app/web")');
  api = py.pyimport('web_api');
  api.date_scrie(py.toPy(date || {}));
  postMessage({ tip: 'gata' });
  // după pornire, în fundal: bibliotecile de export, ca primul export să fie rapid (fără să întârzie interfața)
  setTimeout(() => { asigura(LIB_XLSX, true).then(() => asigura(LIB_DXF, true)).catch(() => { }); }, 8000);
}

const SCRIU_DATE = new Set(['/api/preturi', '/api/preturi/import', '/api/profile']);
onmessage = async e => {
  const d = e.data;
  if (d.tip === 'start') { bootP = boot(d.date).catch(err => postMessage({ tip: 'eroare', text: String(err && err.message || err) })); return; }
  await bootP;
  try {
    for (const lib of NEVOI[d.cale] || []) await asigura(lib);
    const r = api.cerere(d.metoda, d.cale, d.corp);
    const status = r.get(0), antete = r.get(1).toJs({ dict_converter: Object.fromEntries }), corp = r.get(2).toJs();
    r.destroy();
    postMessage({ id: d.id, status, antete, corp }, [corp.buffer]);
    if (d.metoda === 'POST' && SCRIU_DATE.has(d.cale) && status === 200) postMessage({ tip: 'date', date: api.date_citeste().toJs({ dict_converter: Object.fromEntries }) });
  } catch (err) {
    const corp = new TextEncoder().encode(JSON.stringify({ eroare: String(err && err.message || err).split('\n').slice(-2).join(' ') }));
    postMessage({ id: d.id, status: 500, antete: { 'Content-Type': 'application/json' }, corp }, [corp.buffer]);
  }
};
