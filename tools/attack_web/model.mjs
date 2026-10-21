// Preview geometry only; target contact is a visual proxy, not a damage simulation.
export function angles(recipe) {
  const n=({straight:1,lob:1,starfruit:5})[recipe.pattern]??recipe.count;
  return Array.from({length:n},(_,i)=>{
    const base=recipe.pattern==='starfruit'?[330,270,180,90,30][i]:(recipe.pattern==='ring'||recipe.pattern==='fan'&&recipe.spread===360)?360*i/n:recipe.pattern==='fan'&&n>1?-recipe.spread/2+recipe.spread*i/(n-1):0;
    const a=recipe.pattern==='lob'?0:((base+(recipe.direction??0))%360+360)%360;
    return a>180?a-360:a;
  });
}
export function shotTimes(recipe) {
  return angles(recipe).map((_,i)=>['straight','lob'].includes(recipe.pattern)?0:Math.round(i*(recipe.shotDelaySeconds??0)*1e8)/1e8);
}
export function launches(recipe,origin,target=null) {
  const directions=angles(recipe);
  const frame=recipe.ammo==='homing'&&recipe.trackingStrength===0&&target&&recipe.pattern!=='lob'?Math.atan2(target[1]-origin[1],target[0]-origin[0]):0;
  return directions.map((degrees,i)=>{
    const angle=degrees*Math.PI/180+frame,side=recipe.pattern==='parallel'?(i-(directions.length-1)/2)*recipe.spacing:0;
    const port=recipe.originShotOffsets?.[i]??[0,0],turn=(recipe.direction??0)*Math.PI/180+frame;
    return {x:port[0]*Math.cos(turn)-port[1]*Math.sin(turn)+origin[0]+Math.cos(angle)*recipe.radius-Math.sin(angle)*side,y:port[0]*Math.sin(turn)+port[1]*Math.cos(turn)+origin[1]+Math.sin(angle)*recipe.radius+Math.cos(angle)*side,angle};
  });
}
export function catapult(origin,plant,target,speedScale=1) {
  const gravity=2000,height=300,launchHeight=Math.max(0,plant[1]+20-origin[1]);
  const flightTime=Math.sqrt(2*height/gravity)+Math.sqrt(2*(height+launchHeight)/gravity);
  const duration=flightTime/speedScale,g=gravity*speedScale**2;
  return {gravity:g,flightTime:duration,vx:(target[0]-origin[0])/duration,vy:(target[1]-origin[1])/duration-.5*g*duration};
}
export function steer(angle,wanted,dt,strength=2) {
  if(strength===0)return angle;
  if(strength>=2)return wanted;
  const f=Math.max(0,strength-1),maximum=strength<=1?120*strength:120+1320*f,response=strength<=1?3*strength:3+21*f,falloff=strength<=1?2:2-1.5*f;
  const error = Math.atan2(Math.sin(wanted-angle),Math.cos(wanted-angle));
  const alignment=.05+.95*Math.pow(Math.max(0,Math.cos(Math.abs(error)/2)),falloff);
  const correction=error*(-Math.expm1(-response*alignment*dt)), cap=maximum*Math.PI/180*dt;
  return angle+Math.max(-cap,Math.min(cap,correction));
}
export function touchesTarget(x,y,dx,dy,target,rect=[-20,-40,40,80],halfSize=[15,15]) {
  // Same segment-vs-expanded-AABB geometry as the released swept hit check.
  let enter=0,exit=1;
  for(const [origin,motion,lo,hi] of [
    [x,dx,target[0]+rect[0]-halfSize[0],target[0]+rect[0]+rect[2]+halfSize[0]],
    [y,dy,target[1]+rect[1]-halfSize[1],target[1]+rect[1]+rect[3]+halfSize[1]]]){
    if(Math.abs(motion)<1e-12){if(origin<lo||origin>hi)return false;continue;}
    let a=(lo-origin)/motion,b=(hi-origin)/motion;if(a>b)[a,b]=[b,a];
    enter=Math.max(enter,a);exit=Math.min(exit,b);if(enter>exit)return false;
  }
  return true;
}
export class Preview {
  constructor(recipe,origin,target,width=1080,height=600,gridSize=[80,98],plant=origin,targetHitBox=[-20,-40,40,80]) { this.reset(recipe,origin,target,width,height,gridSize,plant,targetHitBox); }
  reset(recipe,origin,target,width=1080,height=600,gridSize=[80,98],plant=origin,targetHitBox=[-20,-40,40,80]) {
    this.targetHitBox=[...targetHitBox];
    this.plant=[...plant];
    this.gridSize=gridSize;
    this.recipe=structuredClone(recipe);this.origin=[...origin];this.target=[...target];this.width=width;this.height=height;
    this.bullets=[];this.time=0;this.next=0;this.emitted=0;this.evicted=0;this.rounds=0;this.pending=[];
  }
  spawn(index) {
    const shot=launches(this.recipe,this.origin,this.target)[index];
    const heading=shot.angle+(this.recipe.angleOffset??0)*Math.PI/180;
    this.bullets.push({...shot,index,angle:heading,born:this.time,age:0,travelCells:0,ballistics:this.recipe.pattern==='lob'?catapult([shot.x,shot.y],this.plant,this.target,this.recipe.speed/300):null});
    const b=this.bullets.at(-1);
    if(this.recipe.pattern==='parallel'&&this.recipe.deploymentSeconds>0){
      const side=(index-(angles(this.recipe).length-1)/2)*this.recipe.spacing;
      b.deployment={from:[shot.x+Math.sin(shot.angle)*side,shot.y-Math.cos(shot.angle)*side],to:[shot.x,shot.y],elapsed:0,duration:this.recipe.deploymentSeconds};
      [b.x,b.y]=b.deployment.from;b.canHit=false;
    }
    this.emitted++;
    if(this.bullets.length>1000){this.bullets.splice(0,50);this.evicted+=50;}
  }
  flushPending() {
    while(this.pending.length&&this.pending[0].at<=this.time+1e-9)this.spawn(this.pending.shift().index);
  }
  volley() {
    for(const [index,offset] of shotTimes(this.recipe).entries())this.pending.push({at:this.time+offset,index});
    this.pending.sort((a,b)=>a.at-b.at);this.flushPending();this.rounds++;
  }
  dispatch() {
    while(this.next<=this.time+1e-9){this.volley();this.next+=this.recipe.intervalSeconds;}
    this.flushPending();
  }
  step(dt,target=this.target) {
    const end=this.time+Math.min(.05,Math.max(0,dt));this.target=target;
    while(this.time<end-1e-9) {
      this.dispatch();
      const h=Math.min(1/120,end-this.time,Math.max(1e-8,this.next-this.time),Math.max(1e-8,(this.pending[0]?.at??Infinity)-this.time));
      for(const b of this.bullets){
        let motionStep=h;
        if(b.deployment){
          const d=b.deployment,used=Math.min(h,d.duration-d.elapsed);d.elapsed+=used;
          const k=Math.min(1,d.elapsed/d.duration);b.x=d.from[0]+(d.to[0]-d.from[0])*k;b.y=d.from[1]+(d.to[1]-d.from[1])*k;
          if(k<1-1e-9)continue;
          b.deployment=null;b.canHit=true;motionStep-=used;if(motionStep<1e-9)continue;
        }
        if(b.ballistics){
          const t=b.ballistics,step=Math.min(h,t.flightTime-b.age);
          b.x+=t.vx*step;b.y+=t.vy*step+.5*t.gravity*step*step;t.vy+=t.gravity*step;b.age+=step;
          continue;
        }
        const dx=Math.cos(b.angle)*this.recipe.speed*motionStep,dy=Math.sin(b.angle)*this.recipe.speed*motionStep;
        b.reached=touchesTarget(b.x,b.y,dx,dy,target,this.targetHitBox);
        b.x+=dx;b.y+=dy;b.travelCells+=Math.hypot(dx/this.gridSize[0],dy/this.gridSize[1]);
        if(this.recipe.ammo==='homing') b.angle=steer(b.angle,Math.atan2(target[1]-b.y,target[0]-b.x),motionStep,this.recipe.trackingStrength??2);
      }
      this.time+=h;
      this.bullets=this.bullets.filter(b=>!b.reached&&(b.ballistics?b.age<b.ballistics.flightTime-1e-9:(!this.recipe.rangeCells||b.travelCells<this.recipe.rangeCells-1e-9)&&(this.recipe.ammo==='homing'&&this.recipe.trackingStrength>=2||b.x>-256&&b.x<this.width+256&&b.y>-256&&b.y<this.height+256)));
    }
    this.dispatch();
  }
}
