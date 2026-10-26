const sharp=require('sharp');
(async()=>{for(const f of process.argv.slice(2)){await sharp(__dirname+'/'+f+'.svg',{density:110}).flatten({background:'#fff'}).png().toFile(__dirname+'/'+f+'.png');}})();
