const assert=require('node:assert/strict'),M=require('./load-engine.cjs').Music;
const raw={candidate:'whorl',ridge_count:41,minutiae:[{type:'ending',x:0,y:.5},{type:'bifurcation',x:.25,y:.3},{type:'dot',x:.875,y:.2}]};
const f=M.validate(raw),p={id:'a',feature:f};
assert.equal(M.compose([p]).bpm,102.5,'fractional BPM must not be rounded or clamped');
for(const n of [1,10,40,400])assert.equal(M.compose([{id:'a',feature:{...f,ridgeCount:n}}]).bpm,n*2.5);
for(const candidate of ['arch','loop','whorl']){
 const player={id:'a',feature:{...f,candidate}},score=M.compose([player]);
 assert.equal(score.genre,M.genres[candidate]);assert(score.events.some(e=>e.voice==='kick'));assert(score.events.some(e=>e.voice==='snare'));assert(score.events.some(e=>e.voice==='hat'));
 for(let i=0;i<3;i++){const e=score.events.find(e=>e.minutiaIndex===i);assert(e,`missing minutia ${i}`);assert.equal(e.owner,'a');assert.equal(e.voice,M.drumMap[raw.minutiae[i].type]);}
 const pcm=M.render(score);assert(pcm.every(Number.isFinite));assert(pcm.some(v=>Math.abs(v)>.03));assert(pcm.every(v=>Math.abs(v)<=.901));assert.equal(M.wav(pcm).byteLength,44+pcm.length*2);
}
const moved=M.compose([{...p,feature:{...f,minutiae:f.minutiae.map((m,i)=>i===0?{...m,x:.5}:m)}}]);
assert.equal(M.compose([p]).events.find(e=>e.minutiaIndex===0).time,0);assert.equal(moved.events.find(e=>e.minutiaIndex===0).time,2*60/102.5);
const hip=M.compose([{...p,feature:{...f,candidate:'arch',minutiae:[{type:'ending',x:1/16,y:.5}]}}]);assert(Math.abs(hip.events[0].time-(.25+.12)*60/102.5)<1e-10);
const q={id:'b',feature:{...f,candidate:'loop',ridgeCount:48}};const duo=M.compose([p,q]);assert.equal(duo.bpm,(41+48)/2*2.5);assert.equal(duo.genre,'テクノ');assert.equal(M.compose([q,p]).genre,'ハウス');for(const id of ['a','b'])assert(duo.events.some(e=>e.owner===id&&e.minutiaIndex!==undefined));
const low=M.compose([{...p,feature:{...f,ridgeCount:1}}]);assert.equal(low.bpm,2.5);assert.equal(low.duration,96);for(let i=0;i<3;i++)assert(low.events.some(e=>e.minutiaIndex===i));
assert.deepEqual(M.compose([p]),M.compose([p]));assert.notDeepEqual(M.compose([p],0).events,M.compose([p],1).events);
assert.throws(()=>M.validate({candidate:'whorl'}));assert.throws(()=>M.validate({...raw,ridge_count:40.5}));assert.throws(()=>M.validate({...raw,ridge_count:0}));assert.throws(()=>M.validate({...raw,decision:'retake'}));assert.throws(()=>M.validate({...raw,quality:{readable:false}}));assert.throws(()=>M.validate({...raw,minutiae:[]}));assert.throws(()=>M.validate({...raw,minutiae:[{type:'ending',x:2,y:0}]}));assert.throws(()=>M.validate({...raw,minutiae:[{type:'unknown',x:0,y:0}]}));assert.throws(()=>M.validate({...raw,minutiae:[{type:'ending',x:NaN,y:0}]}));
const legacy=M.validate({candidate:'loop',decision:'reference_candidate',quality:{readable:true}},true);assert.equal(legacy.ridgeCount,null);assert.deepEqual(legacy.minutiae,[]);assert.throws(()=>M.requireComplete(legacy));
console.log('PASS: exact ridge x2.5 BPM, fractional and boundary tempos, genre arrangement, all minutia drums, coordinate timing/swing, ensemble mean/lead policy, low-BPM full bar, deterministic audio, WAV and invalid inputs.');
