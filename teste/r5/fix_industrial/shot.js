const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({viewport:{width:2400,height:1700}});
  for (const n of process.argv.slice(2)) {
    let s = fs.readFileSync('/home/claude/sm/teste/r5/fix_industrial/'+n+'.svg','utf8');
    s = s.replace(/width="[\d.]+mm" height="[\d.]+mm"/, 'width="2400" height="1697"');
    await p.setContent('<html><body style="margin:0;background:#fff">'+s+'</body></html>');
    await p.screenshot({path:'/home/claude/sm/teste/r5/fix_industrial/'+n+'.png', timeout:120000});
  }
  await b.close();
})();
