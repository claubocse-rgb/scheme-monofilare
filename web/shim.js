/* Versiunea web: cererile /api/... ale interfeței merg la motorul Python din worker, nu la un server. */
window.SM_WEB = true;
(() => {
  const LS = 'sm.web.date';
  const boot = document.getElementById('sm-boot');
  const bootTxt = document.getElementById('sm-boot-t');
  const w = new Worker('worker.js');
  let seq = 0; const pend = new Map();
  let gata; const ready = new Promise(r => { gata = r; });
  w.onmessage = e => {
    const d = e.data;
    if (d.tip === 'gata') { gata(); bootTxt.textContent = 'Gata.'; setTimeout(() => { boot.hidden = true; }, 600); }
    else if (d.tip === 'progres') { if (boot.hidden && typeof toast === 'function') toast(d.text, { ms: 4000 }); else bootTxt.textContent = d.text; }
    else if (d.tip === 'eroare') { bootTxt.textContent = 'Motorul de calcul nu a pornit: ' + d.text + ' — reîncarcă pagina.'; boot.classList.add('err'); }
    else if (d.tip === 'date') { try { localStorage.setItem(LS, JSON.stringify(d.date)); } catch { } }
    else if (d.id && pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id); }
  };
  w.onerror = e => { bootTxt.textContent = 'Motorul de calcul nu a pornit (' + (e.message || 'eroare') + ') — reîncarcă pagina.'; boot.classList.add('err'); };
  let salvat = {}; try { salvat = JSON.parse(localStorage.getItem(LS) || '{}') || {}; } catch { }
  w.postMessage({ tip: 'start', date: salvat });
  const orig = window.fetch.bind(window);
  window.fetch = async (url, opts = {}) => {
    const u = typeof url === 'string' ? url : url.url;
    if (!u.startsWith('/api/')) return orig(url, opts);
    await ready;
    const b = opts.body; let bytes;
    if (b == null) bytes = new Uint8Array(0);
    else if (typeof b === 'string') bytes = new TextEncoder().encode(b);
    else if (b instanceof Blob) bytes = new Uint8Array(await b.arrayBuffer());
    else if (b instanceof ArrayBuffer) bytes = new Uint8Array(b.slice(0));
    else if (ArrayBuffer.isView(b)) bytes = new Uint8Array(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
    else bytes = new TextEncoder().encode(String(b));
    const id = ++seq;
    const r = await new Promise(res => { pend.set(id, res); w.postMessage({ id, metoda: (opts.method || 'GET').toUpperCase(), cale: u.split('?')[0], corp: bytes }, [bytes.buffer]); });
    return new Response(r.corp, { status: r.status, headers: r.antete });
  };
  // descărcări: prin capabilitatea „downloads” a paginii (browserul gazdă cere confirmarea)
  window.SM_SAVE = async (name, blob) => {
    const dl = window.claude && window.claude.use ? await window.claude.use('downloads') : null;
    if (!dl) {      // pagină obișnuită (ex. GitHub Pages): descărcare directă din browser
      const url = URL.createObjectURL(blob instanceof Blob ? blob : new Blob([blob]));
      const a = document.createElement('a'); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000); return true;
    }
    try { await dl.save({ filename: name, data: blob }); return true; }
    catch (e) {
      if (e && e.code === 'declined') return false;
      if (e && e.code === 'rate_limited') { toast('O confirmare de descărcare e deja deschisă.'); return false; }
      toast('Descărcarea nu a fost permisă aici (' + ((e && e.code) || 'eroare') + ').', { kind: 'warn' }); return false;
    }
  };
})();
