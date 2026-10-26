const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 2380, height: 1684 } });
  const only = process.argv[2] ? process.argv[2].split(',') : null;
  for (const f of fs.readdirSync('planse').filter(x => x.endsWith('.svg'))) {
    if (only && !only.includes(f.replace('.svg',''))) continue;
    const svg = fs.readFileSync('planse/' + f, 'utf8');
    await p.setContent(`<html><body style="margin:0;background:#fff"><div style="width:2380px;height:1684px">${svg.replace(/<\?xml[^>]*>/,'')}</div><style>svg{width:2380px!important;height:1684px!important}</style></body></html>`);
    await p.screenshot({ path: 'planse/' + f.replace('.svg', '.png'), timeout: 60000 });
  }
  await b.close();
})();
