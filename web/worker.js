/* Versiunea web: motorul Python al aplicației rulează în acest worker, prin Pyodide (CPython compilat în WebAssembly). */
// fișierele .whl / .zip sunt publicate cu sufixul .wasm (tip servit de gazdă); cererile le primesc transparent
const _f = self.fetch.bind(self);
self.fetch = (u, o) => { const s = String(u && u.url || u); return _f(/\.(whl|zip)$/.test(s) ? s + '.wasm' : u, o); };
importScripts('pyodide/pyodide.js');

const ROTI = ['typing_extensions-4.16.0-py3-none-any.whl', 'pyparsing-3.3.3-py3-none-any.whl', 'fonttools-4.67.0-py3-none-any.whl',
  'ezdxf-1.4.5-py3-none-any.whl', 'et_xmlfile-2.0.0-py3-none-any.whl', 'openpyxl-3.1.5-py2.py3-none-any.whl'];
let api = null, bootP = null;
const progres = text => postMessage({ tip: 'progres', text });

async function boot(date) {
  const base = new URL('.', self.location.href).href;
  progres('Pornesc Python în browser…');
  const py = await loadPyodide({ indexURL: base + 'pyodide/' });
  progres('Încarc bibliotecile (DXF, Excel)…');
  await py.loadPackage([base + 'pyodide/numpy-1.26.4-cp312-cp312-pyodide_2024_0_wasm32.whl', ...ROTI.map(f => base + 'whl/' + f)]);
  progres('Încarc motorul de calcul…');
  const src = await (await _f(base + 'app_src.json')).json();
  for (const [p, txt] of Object.entries(src)) {
    const full = '/app/' + p; py.FS.mkdirTree(full.slice(0, full.lastIndexOf('/'))); py.FS.writeFile(full, txt);
  }
  py.runPython('import sys; sys.path.insert(0, "/app"); sys.path.insert(0, "/app/web")');
  api = py.pyimport('web_api');
  api.date_scrie(py.toPy(date || {}));
  postMessage({ tip: 'gata' });
}

const SCRIU_DATE = new Set(['/api/preturi', '/api/preturi/import', '/api/profile']);
onmessage = async e => {
  const d = e.data;
  if (d.tip === 'start') { bootP = boot(d.date).catch(err => postMessage({ tip: 'eroare', text: String(err && err.message || err) })); return; }
  await bootP;
  try {
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
