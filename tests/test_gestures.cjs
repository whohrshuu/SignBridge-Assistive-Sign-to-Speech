const assert=require('node:assert/strict');
const G=require('../gestures.js');
function pose(bits,thumb=false,spread=false,direction='up'){
 const p=Array.from({length:21},()=>({x:0,y:1,z:0}));
 const bases=[[-.28,.62],[-.09,.55],[.12,.59],[.3,.69]];
 bases.forEach(([x,y],f)=>{const i=5+4*f;p[i]={x,y,z:0};
  if(bits[f]){const dx=spread?(f===0?-.32:f===1?.25:0):0;
   p[i+1]={x:x+dx*.4,y:y-.24,z:0};p[i+2]={x:x+dx*.7,y:y-.4,z:0};p[i+3]={x:x+dx,y:y-.55,z:0};
  }else{p[i+1]={x,y:y-.19,z:0};p[i+2]={x:x+.02,y:y-.03,z:0};p[i+3]={x:x+.03,y:y+.14,z:0};}
 });
 p[1]={x:-.25,y:.93,z:0};p[2]={x:-.45,y:.8,z:0};
 if(thumb){p[3]={x:-.67,y:.6,z:0};p[4]={x:-.92,y:.36,z:0};}
 else{p[3]={x:-.29,y:.67,z:0};p[4]={x:-.08,y:.67,z:0};}
 if(direction==='thumbup'){p[3]={x:-.45,y:.25,z:0};p[4]={x:-.45,y:-.3,z:0};}
 if(direction==='thumbdown'){p[3]={x:-.45,y:1.25,z:0};p[4]={x:-.45,y:1.8,z:0};}
 return p;
}
const poses={open_palm:pose([1,1,1,1],true),four_fingers:pose([1,1,1,1]),closed_fist:pose([0,0,0,0]),one_finger:pose([1,0,0,0]),two_fingers:pose([1,1,0,0]),v_sign:pose([1,1,0,0],false,true),three_fingers:pose([1,1,1,0]),phone_gesture:pose([0,0,0,1],true),thumbs_up:pose([0,0,0,0],true,false,'thumbup'),thumbs_down:pose([0,0,0,0],true,false,'thumbdown')};
let n=0;
for(const [label,p] of Object.entries(poses))for(const scale of [.08,.16,.3])for(const rot of [-.35,0,.35])for(const mirror of [-1,1])for(const aspect of [1,4/3,16/9]){
 const hand=p.map(v=>({x:(.6+scale*mirror*(v.x*Math.cos(rot)-v.y*Math.sin(rot)))/aspect,y:.35+scale*(v.x*Math.sin(rot)+v.y*Math.cos(rot)),z:0}));
 assert.equal(G.classify(hand,aspect),label,`${label}: ${scale}, ${rot}, ${mirror}, ${aspect}`);n++;
}
for(const [g,phrase] of Object.entries(G.single))assert.equal(G.mapHands([g]).phrase,phrase);
for(const [pair,phrase] of Object.entries(G.combo)){
 const g=pair.split(' + ');assert.equal(G.mapHands(g).phrase,phrase);assert.equal(G.mapHands([...g].reverse()).phrase,phrase);
}
for(const pair of [['four_fingers','open_palm'],['open_palm','four_fingers'],['four_fingers','four_fingers']])assert.equal(G.mapHands(pair).phrase,'I Need Assistance');
assert.equal(G.mapHands(['open_palm','unknown']).phrase,'Unknown Gesture');
assert.equal(G.classify([]),'unknown');assert.equal(G.classify(Array(21).fill({x:0,y:0})),'unknown');
const s=new G.Stabilizer();assert.equal(s.update('I Need Assistance',0,2),false);assert.equal(s.update('I Need Assistance',610,2),true);assert.equal(s.update('I Need Assistance',6000,2),false);
s.update('',6100,0);s.update('',6600,0);s.update('I Need Assistance',6700,2);assert.equal(s.update('I Need Assistance',7310,2),true);
const t=new G.Stabilizer();t.update('Hello',0,1);assert.equal(t.update('Hello',700,1),false);t.update('I Need Assistance',750,2);assert.equal(t.update('I Need Assistance',1360,2),true);
console.log(`PASS: ${n} transformed pose cases, all 14 phrase mappings, relaxed-thumb assistance, unknown-hand rejection, release/repeat and combo precedence.`);
module.exports={poses};
