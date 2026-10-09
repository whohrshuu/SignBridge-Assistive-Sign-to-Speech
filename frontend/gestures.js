/* Shared, testable geometry for custom phrase shortcuts (not ASL translation). */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.SignBridgeGestures=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
  const single={thumbs_up:'Yes',thumbs_down:'No',open_palm:'Hello',closed_fist:'Stop',one_finger:'Help',two_fingers:'Water',three_fingers:'Food',four_fingers:'Thank You',phone_gesture:'Call',v_sign:'Wait'};
  const combo={'open_palm + open_palm':'I Need Assistance','closed_fist + open_palm':'Emergency','open_palm + two_fingers':'Please Wait','open_palm + thumbs_up':'Call Family'};
  const d=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
  function angle(a,b,c){const u=[a.x-b.x,a.y-b.y],v=[c.x-b.x,c.y-b.y];const n=Math.hypot(...u)*Math.hypot(...v);return n<1e-8?0:Math.acos(Math.max(-1,Math.min(1,(u[0]*v[0]+u[1]*v[1])/n)))*180/Math.PI;}
  function classify(input,aspect=1){
    if(!Array.isArray(input)||input.length!==21||input.some(p=>!p||!Number.isFinite(p.x)||!Number.isFinite(p.y)))return 'unknown';
    if(!Number.isFinite(aspect)||aspect<=0)return 'unknown';
    const p=input.map(v=>({x:v.x*aspect,y:v.y})),w=p[0];
    const width=d(p[5],p[17]),scale=Math.max(width,d(w,p[9]));
    if(scale<.015)return 'unknown';
    const extended=[5,9,13,17].map(i=>angle(p[i],p[i+1],p[i+3])>150&&d(w,p[i+3])>d(w,p[i+1])*1.08);
    const [i,m,r,k]=extended, count=extended.filter(Boolean).length;
    const thumb=angle(p[2],p[3],p[4])>140&&d(p[4],p[5])>width*.72&&d(p[4],p[17])>width*1.25;
    if(count===0&&thumb){
      if(p[4].y<p[2].y-scale*.45)return 'thumbs_up';
      if(p[4].y>p[2].y+scale*.45)return 'thumbs_down';
    }
    if(count===4)return thumb?'open_palm':'four_fingers';
    if(i&&m&&!r&&!k&&!thumb){
      // Angular separation is independent of how far the hand is from the camera.
      const a={x:p[8].x-p[5].x,y:p[8].y-p[5].y},b={x:p[12].x-p[9].x,y:p[12].y-p[9].y};
      return angle(a,{x:0,y:0},b)>17?'v_sign':'two_fingers';
    }
    if(i&&!m&&!r&&!k&&!thumb)return 'one_finger';
    if(i&&m&&r&&!k&&!thumb)return 'three_fingers';
    if(!i&&!m&&!r&&k&&thumb)return 'phone_gesture';
    if(count===0&&!thumb)return 'closed_fist';
    return 'unknown';
  }
  function mapHands(hands){
    const gestures=hands.map(h=>typeof h==='string'?h:h.gesture);
    const debugText=gestures.map((g,i)=>`Hand ${i+1}: ${g}`).join(' | ');
    if(!gestures.length)return {phrase:'',debugText:'0 hands',usedGestures:[]};
    if(gestures.length===2){
      // For two-hand shortcuts, an open four-finger palm may have a relaxed/tucked thumb.
      const g=gestures.map(x=>x==='four_fingers'?'open_palm':x);
      const phrase=combo[g.join(' + ')]||combo[g.slice().reverse().join(' + ')]||'Unknown Gesture';
      return {phrase,debugText:phrase==='Unknown Gesture'?debugText+' · keep both complete hands visible':debugText,usedGestures:gestures};
    }
    if(gestures.length!==1)return {phrase:'Unknown Gesture',debugText,usedGestures:gestures};
    return {phrase:single[gestures[0]]||'Unknown Gesture',debugText,usedGestures:gestures};
  }
  class Stabilizer{
    constructor(){this.reset();}
    reset(){this.candidate='';this.since=0;this.last='';this.gapSince=null;}
    update(phrase,now,hands=1){
      const known=phrase&&phrase!=='Unknown Gesture';
      if(!known){
        if(this.gapSince===null)this.gapSince=now;
        if(now-this.gapSince>=450){this.last='';this.candidate='';}
        return false;
      }
      if(this.gapSince!==null){if(now-this.gapSince>180)this.candidate='';this.gapSince=null;}
      if(phrase!==this.candidate){this.candidate=phrase;this.since=now;return false;}
      // Longer single-hand dwell gives the second hand time to enter the image.
      if(now-this.since>=(hands===2?600:850)&&phrase!==this.last){this.last=phrase;return true;}
      return false;
    }
  }
  return {classify,mapHands,Stabilizer,single,combo};
});
