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
  // F.9 citirea avansată: fără server, apelul către Claude îl face browserul, cu cheia utilizatorului ținută
  // DOAR aici (memorie; localStorage numai la „ține minte”). Worker-ul Python face fuziunea cu regulile locale.
  const LS_CHEIE = 'sm.web.cheie_anthropic';
  let CHEIE = null; try { CHEIE = localStorage.getItem(LS_CHEIE) || null; } catch { }
  const jsonRasp = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { 'Content-Type': 'application/json; charset=utf-8' } });
  const laWorker = async (cale, metoda, obj) => {
    const bytes = new TextEncoder().encode(obj == null ? '' : JSON.stringify(obj));
    const id = ++seq;
    const r = await new Promise(res => { pend.set(id, res); w.postMessage({ id, metoda, cale, corp: bytes }, [bytes.buffer]); });
    return JSON.parse(new TextDecoder().decode(r.corp));
  };
  async function chatAvansat(corp) {
    const c = await laWorker('/api/chat/cerere', 'POST', { text: corp.text });
    try {
      const r = await orig(c.url, { method: 'POST', body: JSON.stringify(c.corp), headers: {
        'content-type': 'application/json', 'x-api-key': CHEIE, 'anthropic-version': c.versiune, 'anthropic-beta': c.beta,
        'anthropic-dangerous-direct-browser-access': 'true' } });
      const j = await r.json().catch(() => null);
      if (!r.ok || !j) throw new Error('HTTP ' + r.status + (j && j.error && j.error.message ? ': ' + j.error.message : ''));
      return laWorker('/api/chat', 'POST', Object.assign({}, corp, { raspuns_llm: j }));
    } catch (e) {
      return laWorker('/api/chat', 'POST', Object.assign({}, corp, { claude: false, eroare_llm: 'apel eșuat (' + (e && e.message || e) + ')' }));
    }
  }
  window.fetch = async (url, opts = {}) => {
    const u = typeof url === 'string' ? url : url.url;
    if (!u.startsWith('/api/')) return orig(url, opts);
    await ready;
    const cale0 = u.split('?')[0];
    if (cale0 === '/api/setari/cheie') {
      let d = {}; try { d = JSON.parse(opts.body || '{}'); } catch { }
      CHEIE = String(d.cheie || '').trim() || null;
      try { if (CHEIE && d.pastreaza) localStorage.setItem(LS_CHEIE, CHEIE); else localStorage.removeItem(LS_CHEIE); } catch { }
      return jsonRasp({ claude: !!CHEIE, claude_sursa: CHEIE ? 'browser' : null });
    }
    if (cale0 === '/api/info') {
      const i = await laWorker('/api/info', 'GET');
      return jsonRasp(Object.assign(i, { claude: !!CHEIE, claude_sursa: CHEIE ? 'browser' : null }));
    }
    if (cale0 === '/api/chat' && typeof opts.body === 'string') {
      let d = null; try { d = JSON.parse(opts.body); } catch { }
      if (d && CHEIE && d.claude !== false && d.raspuns_llm == null) return jsonRasp(await chatAvansat(d));
    }
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
