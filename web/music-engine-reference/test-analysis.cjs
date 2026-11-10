const assert=require('node:assert/strict'),{Fingerprint:F,Music:M}=require('./load-engine.cjs');
function fixture(label,rotation=0){const n=384,g=new Float32Array(n*n);for(let y=0;y<n;y++)for(let x=0;x<n;x++){const a=(x-n/2)/(n/2),b=(y-n/2)/(n/2),u=a*Math.cos(rotation)-b*Math.sin(rotation),v=a*Math.sin(rotation)+b*Math.cos(rotation);let phase;if(label==='arch')phase=v+.5*Math.exp(-u*u/.4);else if(label==='loop')phase=Math.sqrt(u*u+(v+.2)**2+.004)+1.15*(v+.2);else phase=Math.sqrt(u*u+v*v+.01);g[y*n+x]=.5+.32*Math.cos(2*Math.PI*11*phase)+.025*a;}return g;}
let reports=0;
for(const label of ['arch','loop','whorl'])for(const rotation of [-.18,0,.18]){const result=F.analyze(fixture(label,rotation),384,384,()=>reports++);assert.equal(result.candidate,label);assert(result.ridgeCount>=4);assert(result.minutiae.every(m=>m.x>=0&&m.x<=1&&m.y>=0&&m.y<=1));assert(result.estimated);assert(result.preview.skeleton.length===384*384);const score=M.compose([{id:'photo',feature:result}]);assert.equal(score.bpm,result.ridgeCount*2.5);assert.equal(score.genre,M.genres[label]);assert(M.render(score).some(x=>Math.abs(x)>.02));}
assert(reports>20);
// Partial observations remain measurements, never invented full-area counts.
const partialMask=new Uint8Array(384*384),partialBinary=new Uint8Array(384*384);
for(let y=100;y<280;y++)for(let x=165;x<205;x++){partialMask[y*384+x]=1;if(x>=180&&x<=183)partialBinary[y*384+x]=1;}
const partial=F.countRidges(partialBinary,partialMask,192,192,0,384,384);
assert.equal(partial.status,'partial');assert.equal(partial.ridgeCount,1);assert(partial.coverage<.45);
const unavailable=F.countRidges(new Uint8Array(384*384),partialMask,192,192,0,384,384);
assert.equal(unavailable.status,'unavailable');assert.equal(unavailable.ridgeCount,null);assert.equal(unavailable.line,null);
// Small but coherent curved texture can proceed, explicitly as a partial estimate.
const limited=fixture('whorl');for(let y=0;y<384;y++)for(let x=0;x<384;x++)if(x<160||x>220||y<160||y>220)limited[y*384+x]=.5;
const limitedResult=F.analyze(limited);assert(limitedResult.analysis.approximate);assert(limitedResult.analysis.quality<35/576);
for(const v of [0,.5,1])assert.throws(()=>F.analyze(new Float32Array(384*384).fill(v)));
const stripes=new Float32Array(384*384);for(let y=0;y<384;y++)for(let x=0;x<384;x++)stripes[y*384+x]=.5+.3*Math.cos(x*.4);assert.throws(()=>F.analyze(stripes));
let seed=3;const noise=Float32Array.from({length:384*384},()=>{seed=Math.imul(seed,1664525)+1013904223|0;return(seed>>>0)/4294967296;});assert.throws(()=>F.analyze(noise));
// Verify topology on known one-pixel ridge endings and a three-way junction.
const n=128,sk=new Uint8Array(n*n),mask=new Uint8Array(n*n).fill(1);for(let x=25;x<100;x++)sk[64*n+x]=1;for(let y=30;y<=64;y++)sk[y*n+64]=1;for(let x=40;x<44;x++)sk[95*n+x]=1;
const result=F.extractMinutiae(sk,mask,n,n);assert.equal(result.minutiae.filter(m=>m.type==='ending').length,3);assert.equal(result.minutiae.filter(m=>m.type==='bifurcation').length,1);assert.equal(result.minutiae.filter(m=>m.type==='dot').length,1);
const rectangle=new Uint8Array(64*64);for(let y=15;y<48;y++)for(let x=20;x<27;x++)rectangle[y*64+x]=1;const thinned=F.thin(rectangle,64,64);assert(thinned.reduce((a,v)=>a+v,0)<rectangle.reduce((a,v)=>a+v,0));assert(thinned.some(Boolean));
console.log('PASS: 9 procedural motif classifications and complete photo-to-audio pipelines; quality rejection (blank/dark/white/stripes/noise); known endpoints, bifurcation and dot; skeleton thinning. Synthetic tests do not establish real-photo accuracy.');
if(process.argv[2]){const fs=require('node:fs'),zlib=require('node:zlib');const g=fixture('loop');for(let y=130;y<150;y++)for(let x=115;x<145;x++)g[y*384+x]=.85;const extracted=F.analyze(g);assert(extracted.minutiae.length>0,'controlled ridge breaks should produce feature candidates');const raw=Buffer.alloc(384*(384*3+1));for(let y=0;y<384;y++){raw[y*(384*3+1)]=0;for(let x=0;x<384;x++){const v=Math.round(g[y*384+x]*255);for(let c=0;c<3;c++)raw[y*(384*3+1)+1+x*3+c]=v;}}
function crc(buf){let crc=-1;for(const b of buf){crc^=b;for(let i=0;i<8;i++)crc=(crc>>>1)^((crc&1)?0xedb88320:0);}return(crc^-1)>>>0;}function chunk(type,b){const t=Buffer.from(type),len=Buffer.alloc(4),sum=Buffer.alloc(4);len.writeUInt32BE(b.length);sum.writeUInt32BE(crc(Buffer.concat([t,b])));return Buffer.concat([len,t,b,sum]);}const h=Buffer.alloc(13);h.writeUInt32BE(384,0);h.writeUInt32BE(384,4);h[8]=8;h[9]=2;fs.writeFileSync(process.argv[2],Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',h),chunk('IDAT',zlib.deflateSync(raw)),chunk('IEND',Buffer.alloc(0))]));}
