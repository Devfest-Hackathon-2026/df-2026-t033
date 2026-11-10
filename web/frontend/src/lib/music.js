/* Fingerprint Symphony: deterministic, browser-local composition. No external samples. */
(function(root){
'use strict';
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const genres={arch:'ヒップホップ',loop:'ハウス',whorl:'テクノ'};
const drumMap={ending:'kick',bifurcation:'snare',dot:'hat',other:'hat'};
function validate(data,allowIncomplete=false){
 if(!data||typeof data!=='object'||Array.isArray(data))throw Error('JSONオブジェクトを選んでください。');
 if(data.decision!==undefined&&data.decision!=='reference_candidate')throw Error('解析が成功していないデータは作曲に使えません。再解析してください。');
 if(data.quality&&data.quality.readable!==true)throw Error('読み取り品質が不足しています。再解析してください。');
 const candidate=data.candidate??data.pattern;
 if(!['arch','loop','whorl'].includes(candidate))throw Error('指紋の種類は arch / loop / whorl が必要です。');
 const f={candidate,source:'json',method:'ridge-minutiae-v2',ridgeCount:null,minutiae:[]};
 if(data.ridge_count!==undefined){if(!Number.isInteger(data.ridge_count)||data.ridge_count<1||data.ridge_count>400)throw Error('ridge_count（隆線数）は1〜400の整数が必要です。');f.ridgeCount=data.ridge_count;}
 if(data.minutiae!==undefined){
  if(!Array.isArray(data.minutiae)||data.minutiae.length<1||data.minutiae.length>512)throw Error('minutiae は1〜512個の特徴点の配列が必要です。');
  f.minutiae=data.minutiae.map(m=>{if(!m||!Object.hasOwn(drumMap,m.type)||typeof m.x!=='number'||typeof m.y!=='number'||!Number.isFinite(m.x)||!Number.isFinite(m.y)||m.x<0||m.x>1||m.y<0||m.y>1)throw Error('特徴点には type（ending / bifurcation / dot / other）と0〜1の座標 x, y が必要です。');return {type:m.type,x:m.x,y:m.y};});
 }
 if(!allowIncomplete)requireComplete(f);
 return f;
}
function requireComplete(f){
 if(!genres[f.candidate])throw Error('指紋の種類を指定してください。');
 if(!Number.isInteger(f.ridgeCount)||f.ridgeCount<1||f.ridgeCount>400)throw Error('隆線数が未取得です。1〜400の整数を入力してください。');
 if(!Array.isArray(f.minutiae)||(!f.minutiae.length&&!(f.source==='image'&&f.estimated===true)))throw Error('特徴点が未取得です。座標を入力してください。');
 // Use the same validator for imported and manually supplemented features.
 if(f.minutiae.length)validate({candidate:f.candidate,ridge_count:f.ridgeCount,minutiae:f.minutiae},true);
 return f;
}
function fingerprintSeed(f){let s=2166136261;for(const c of JSON.stringify([f.candidate,f.ridgeCount,f.minutiae]))s=Math.imul(s^c.charCodeAt(0),16777619);return s>>>0;}
function random(seed){return()=>{seed|=0;seed=seed+0x6D2B79F5|0;let t=Math.imul(seed^seed>>>15,1|seed);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
function settings(players){
 if(!players.length||players.length>3)throw Error('参加者を1〜3人選択してください。');
 players.forEach(p=>requireComplete(p.feature));
 const ridgeMean=players.reduce((sum,p)=>sum+p.feature.ridgeCount,0)/players.length;
 const lead=players[0];
 return {bpm:ridgeMean*2.5,genre:genres[lead.feature.candidate],pattern:lead.feature.candidate,ridgeMean,leadId:lead.id};
}
function compose(players,arrangement=0){
 const config=settings(players),{bpm,pattern}=config;
 const beat=60/bpm,duration=Math.max(players.length===1?8:20,beat*4),events=[];
 const scale=pattern==='arch'?[0,3,5,7,10]:pattern==='loop'?[0,2,5,7,9]:[0,1,5,7,10];
 players.forEach(p=>{
  const f=p.feature,rng=random(fingerprintSeed(f)),melody=Array.from({length:8},()=>scale[Math.floor(rng()*5)]);
  // Every minutia is represented by a drum event. x maps to a 16-step bar;
  // y controls loudness. Exact quantization collisions remain separate events.
  f.minutiae.forEach((m,index)=>{
   const step=Math.min(15,Math.floor(m.x*16)),swing=pattern==='arch'&&step%2?.12:0;
   const offset=(step*.25+swing)*beat;
   for(let time=offset;time<duration-.01;time+=4*beat){const voice=drumMap[m.type];events.push({time,length:Math.min(voice==='hat'?.09:voice==='snare'?.2:.3,duration-time),midi:voice==='kick'?36:voice==='snare'?38:42,gain:(voice==='hat'?.08:.19)*(.5+(1-m.y)*.5)/Math.sqrt(players.length),voice,owner:p.id,minutiaIndex:index,step});}
  });
  const stride=pattern==='whorl'?.25:pattern==='loop'?.5:1;
  for(let i=0;i*beat*stride<duration-.05;i++){
   const time=i*beat*stride+(pattern==='arch'&&i%2?.08*beat:0);if(time>=duration)break;
   events.push({time,length:Math.min(beat*(pattern==='whorl'?.22:.65),duration-time),midi:(pattern==='whorl'?60:72)+melody[(i+arrangement*2)%8],gain:.065/Math.sqrt(players.length),voice:pattern==='whorl'?'acid':pattern==='arch'?'soft':'pluck',owner:p.id});
  }
 });
 for(let b=0;b*beat<duration;b+=pattern==='whorl'?.5:pattern==='loop'?1:2){const chord=[0,5,9,7][Math.floor(b/4)%4],time=b*beat;events.push({time,length:Math.min(beat*.8,duration-time),midi:36+chord,gain:.1,voice:'bass',owner:'ensemble'});}
 if(pattern!=='whorl')for(let b=0;b*beat<duration;b+=4){for(const n of [48,55,60])events.push({time:b*beat,length:Math.min(beat*3.8,duration-b*beat),midi:n+[0,5,9,7][Math.floor(b/4)%4],gain:.018,voice:'pad',owner:'ensemble'});}
 return {events,duration,...config,arrangement,owners:players.map(p=>p.id),personalBpms:players.map(p=>({owner:p.id,bpm:p.feature.ridgeCount*2.5})),method:'ridge-minutiae-v2'};
}
function render(score,sampleRate=22050){
 const pcm=new Float32Array(Math.ceil(score.duration*sampleRate));
 for(const e of score.events){const start=Math.floor(e.time*sampleRate),len=Math.min(Math.floor(e.length*sampleRate),pcm.length-start);const freq=440*Math.pow(2,(e.midi-69)/12);for(let i=0;i<len;i++){const t=i/sampleRate,u=i/len,attack=Math.min(1,t/.018);let env=attack*Math.pow(1-u,e.voice==='pad'?1.3:2.5),v;
 if(e.voice==='kick')v=Math.sin(2*Math.PI*(48*t+7*(1-Math.exp(-t*28))))*Math.exp(-t*22);
 else if(e.voice==='snare')v=(.7*Math.sin(i*123.45)*Math.sin(i*37.13)+.3*Math.sin(2*Math.PI*185*t))*Math.exp(-t*16);
 else if(e.voice==='hat')v=Math.sin(i*123.45)*Math.sin(i*37.13)*Math.exp(-t*38);
 else {const a=2*Math.PI*freq*t;v=Math.sin(a);if(e.voice==='bell')v=.7*v+.3*Math.sin(a*2.003)*Math.exp(-t*8);if(e.voice==='pluck')v=.8*v+.16*Math.sin(a*2)+.04*Math.sin(a*3);if(e.voice==='soft')v=.85*v+.15*Math.sin(a*3);if(e.voice==='acid')v=Math.tanh((Math.sin(a)+.5*Math.sin(a*2)+.3*Math.sin(a*3))*2)*Math.exp(-t*4);}
 pcm[start+i]+=v*env*e.gain;}}
 // Fade the edges and normalize only if required.
 let peak=0;for(let i=0;i<pcm.length;i++){pcm[i]*=Math.min(1,i/(sampleRate*.02),(pcm.length-i)/(sampleRate*.2));peak=Math.max(peak,Math.abs(pcm[i]));}if(peak>.9)for(let i=0;i<pcm.length;i++)pcm[i]*=.9/peak;
 return pcm;
}
function wav(pcm,sampleRate=22050){const buffer=new ArrayBuffer(44+pcm.length*2),v=new DataView(buffer);const word=(o,s)=>{for(let i=0;i<s.length;i++)v.setUint8(o+i,s.charCodeAt(i));};word(0,'RIFF');v.setUint32(4,36+pcm.length*2,true);word(8,'WAVE');word(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,sampleRate,true);v.setUint32(28,sampleRate*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);word(36,'data');v.setUint32(40,pcm.length*2,true);for(let i=0;i<pcm.length;i++)v.setInt16(44+i*2,clamp(pcm[i],-1,1)*32767,true);return buffer;}
const api={validate,requireComplete,settings,genres,drumMap,compose,render,wav,fingerprintSeed};if(typeof module!=='undefined')module.exports=api;else root.Music=api;
})(typeof window==='undefined'?globalThis:window);

export const Music = globalThis.Music;
