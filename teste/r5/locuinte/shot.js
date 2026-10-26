const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 2380, height: 1684 } });
  for (const f of fs.readdirSync('planse').filter(x => x.endsWith('.svg'))) {
    const svg = fs.readFileSync('planse/' + f, 'utf8');
    await p.setContent(`<html><body style="margin:0;background:#fff"><div style="width:2380px;height:1684px">${svg.replace(/<\?xml[^>]*>/,'')}</div><style>svg{width:2380px!important;height:1684px!important}</style></body></html>`);
    await p.screenshot({ path: 'planse/' + f.replace('.svg', '.png'), timeout: 60000 });
  }
  await b.close();
})();
