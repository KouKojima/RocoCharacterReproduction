import * as THREE from 'three';
import {loadAsset} from './assets.js';

const pUE=(x,y,z,out)=>out.set(x*.01,z*.01,-y*.01);
const qUE=(x,y,z,w,out)=>out.set(x,z,-y,w).normalize();
const sUE=(x,y,z,out)=>out.set(x,z,y);
const identityQ=new THREE.Quaternion();

export async function loadNativeAnimation(model,root='assets/animation/'){
 const [manifest,rig,skinBuffer,poses,authored]=await Promise.all([loadAsset(root+'manifest.json',true),loadAsset(root+'rig.json',true),loadAsset(root+'skin.bin'),loadAsset(root+'poses.json',true),loadAsset(root+'authored-curves.json',true)]);
 const clips=new Map();
 await Promise.all(manifest.clips.map(async meta=>{
  const b=await loadAsset(root+meta.file),head=new DataView(b);
  if(head.getUint32(0,true)!==0x414e524e)throw Error('动画数据头不正确：'+meta.name);
  const frames=head.getUint32(4,true),bones=head.getUint32(8,true),duration=head.getFloat32(12,true);
  if(bones!==rig.bones.length)throw Error('动画骨骼数量不匹配：'+meta.name);
  clips.set(meta.name,{...meta,frames,bones,duration,data:new Float32Array(b,16)});
 }));
 return new NativeAnimator(model,manifest,rig,skinBuffer,poses,clips,authored);
}

export function evaluateSourceCurve(curve,time){
 const keys=curve.keys;if(!keys.length)return 0;if(time<=keys[0][0])return keys[0][1];const last=keys[keys.length-1];if(time>=last[0])return last[1];
 let lo=0,hi=keys.length-1;while(hi-lo>1){const m=(lo+hi)>>1;if(keys[m][0]<=time)lo=m;else hi=m;}
 const a=keys[lo],b=keys[hi],d=b[0]-a[0],u=(time-a[0])/d;
 if(curve.interpolation==='constant')return a[1];if(curve.interpolation==='linear')return a[1]+u*(b[1]-a[1]);
 const u2=u*u,u3=u2*u;return (2*u3-3*u2+1)*a[1]+(u3-2*u2+u)*d*a[3]+(-2*u3+3*u2)*b[1]+(u3-u2)*d*b[2];
}

class NativeAnimator{
 constructor(model,manifest,rig,skinBuffer,poses,clips,authored){
  Object.assign(this,{model,manifest,rig,poses,clips,authored});this.body='World_Idle';this.face='none';this.pose='Reference';this.poseWeight=1;this.faceWeight=1;this.loop=true;this.inPlace=true;this.time=0;this.faceTime=0;this.speed=1;this.playing=true;this.dirty=true;this.updated=false;this.blinkCurve=authored.curves.find(c=>c.name==='EyeBlink');this.facial=null;this.facialCurves=null;this.lastFacial=null;
  const h=new Uint32Array(skinBuffer,0,4);if(h[0]!==0x534b524e||h[1]!==model.metadata.vertexCount||h[2]!==rig.bones.length)throw Error('蒙皮与模型不匹配');
  this.influences=h[3];const dv=new DataView(skinBuffer);this.ids=new Uint16Array(h[1]*h[3]);this.weights=new Float32Array(h[1]*h[3]);
  for(let i=0;i<h[1];i++)for(let j=0;j<h[3];j++){this.ids[i*h[3]+j]=dv.getUint16(16+i*24+j*2,true);this.weights[i*h[3]+j]=dv.getFloat32(16+i*24+8+j*4,true);}
  this.local=rig.bones.map(b=>({p:pUE(...b.position,new THREE.Vector3()),q:qUE(...b.quaternion,new THREE.Quaternion()),s:sUE(...b.scale,new THREE.Vector3())}));
  this.reference=this.local.map(t=>({p:t.p.clone(),q:t.q.clone(),s:t.s.clone()}));
  this.world=rig.bones.map(()=>new THREE.Matrix4());this.inverseBind=rig.bones.map(()=>new THREE.Matrix4());this.skin=rig.bones.map(()=>new THREE.Matrix4());this.tmpMatrix=new THREE.Matrix4();this.tmpP=new THREE.Vector3();this.tmpQ=new THREE.Quaternion();this.tmpS=new THREE.Vector3();this.tmpDelta=new THREE.Quaternion();
  this.computeWorld();for(let i=0;i<rig.bones.length;i++)this.inverseBind[i].copy(this.world[i]).invert();
  this.poseByName=new Map(poses.poses.map(p=>[p.name,p]));this.faceMask=manifest.facialBoneIndices;
  this.headIndex=rig.bones.findIndex(b=>b.name==='Bip001-Head');this.headDelta=new THREE.Matrix3();
  this.baseP=model.raw.positions.slice();this.baseN=model.raw.normals.slice();this.baseT=model.raw.tangents.slice();
  this.positions=new Float32Array(this.baseP);this.normals=new Float32Array(this.baseN);this.tangents=new Float32Array(this.baseT);
  for(const [name,array,size]of [['position',this.positions,3],['normal',this.normals,3],['tangent',this.tangents,4]])model.geometry.setAttribute(name,new THREE.BufferAttribute(array,size).setUsage(THREE.DynamicDrawUsage));
  this.referenceSkinError=this.bindError();this.apply(0);this.skinVertices();
 }
 get duration(){return this.clips.get(this.body)?.duration??0;}
 get faceDuration(){return this.face==='authored_blink'||this.face==='authored_all'?this.authored.sourceDuration:this.clips.get(this.face)?.duration??0;}
 get atEnd(){const d=this.duration||this.faceDuration;return !this.loop&&d>0&&this.time>=d;}
 get displayTime(){return this.clipTime(this.time,this.duration,this.seekBodyEnd);}
 get displayFaceTime(){return this.clipTime(this.faceTime,this.faceDuration,this.seekFaceEnd);}
 setBody(name){this.body=name;this.time=0;this.seekBodyEnd=false;this.dirty=true;}
 setFace(name){this.face=name;this.faceTime=0;this.seekFaceEnd=false;this.dirty=true;}
 setPose(name){this.pose=name;this.dirty=true;}
 seek(t){this.time=Math.max(t,0);this.faceTime=this.time;this.seekBodyEnd=Math.abs(this.time-this.duration)<1e-6;this.seekFaceEnd=Math.abs(this.faceTime-this.faceDuration)<1e-6;this.dirty=true;}
 seekFace(t){this.faceTime=THREE.MathUtils.clamp(t,0,this.faceDuration);this.seekFaceEnd=Math.abs(this.faceTime-this.faceDuration)<1e-6;this.dirty=true;}
 computeWorld(){
  for(let i=0;i<this.local.length;i++){
   const t=this.local[i],parent=this.rig.bones[i].parent;
   this.world[i].compose(t.p,t.q,t.s);if(parent>=0)this.world[i].premultiply(this.world[parent]);
  }
 }
 resetPose(){for(let i=0;i<this.local.length;i++){this.local[i].p.copy(this.reference[i].p);this.local[i].q.copy(this.reference[i].q);this.local[i].s.copy(this.reference[i].s);}}
 sample(clip,time,index,p,q,s){
  const t=THREE.MathUtils.clamp(time,0,clip.duration),f=t/Math.max(clip.duration,1e-8)*(clip.frames-1),a=Math.floor(f),b=Math.min(a+1,clip.frames-1),alpha=f-a,n=clip.bones,d=clip.data,ia=(a*n+index)*10,ib=(b*n+index)*10;
  pUE(d[ia],d[ia+1],d[ia+2],p);pUE(d[ib],d[ib+1],d[ib+2],this.tmpP2??=new THREE.Vector3());p.lerp(this.tmpP2,alpha);
  qUE(d[ia+3],d[ia+4],d[ia+5],d[ia+6],q);qUE(d[ib+3],d[ib+4],d[ib+5],d[ib+6],this.tmpQ2??=new THREE.Quaternion());q.slerp(this.tmpQ2,alpha).normalize();
  sUE(d[ia+7],d[ia+8],d[ia+9],s);sUE(d[ib+7],d[ib+8],d[ib+9],this.tmpS2??=new THREE.Vector3());s.lerp(this.tmpS2,alpha);
 }
 clipTime(time,duration,ending=false){return ending?duration:this.loop&&duration>0?time%duration:Math.min(time,duration);}
 addPose(pose,weight){
  if(!pose||weight<=0)return;
  for(const b of pose.bones){
   const t=this.local[b.boneIndex],w=weight;
   t.p.x+=b.translationDelta[0]*w;t.p.y+=b.translationDelta[1]*w;t.p.z+=b.translationDelta[2]*w;
   this.tmpDelta.fromArray(b.rotationDelta).normalize();const sign=this.tmpDelta.w>=0?1:-1,weighted=this.tmpQ3??=new THREE.Quaternion();
   // UE4 BlendFromIdentityAndAccumulate: normalized linear quaternion blend.
   weighted.set(this.tmpDelta.x*w,this.tmpDelta.y*w,this.tmpDelta.z*w,this.tmpDelta.w*w+sign*(1-w)).normalize();t.q.premultiply(weighted).normalize();
   t.s.x*=1+b.scaleDelta[0]*w;t.s.y*=1+b.scaleDelta[1]*w;t.s.z*=1+b.scaleDelta[2]*w;
  }
 }
 // ---- original controllerConfig facial curves --------------------------
 setFacial(data){
  if(!data){this.facial=null;this.facialCurves=null;return;}
  this.facial={entries:data.entries,stats:data.stats};
  // The authored _Neg curves are exact mirrors of the positive ones and
  // controllerConfig already expresses that direction with weight -1 on the
  // companion _Neg pose, so sampling both would double-count.
  this.facialCurves=new Map(this.authored.curves.filter(c=>!c.name.endsWith('_Neg')).map(c=>[c.name,c]));
 }
 applyFacial(time,blend){
  if(!this.facial||!this.facialCurves)return;
  const byPose=new Map();let used=0,negativeSkipped=0,jawOpen=0,blinkScale=0,maxWeight=0,missing=0;
  for(const [name,attrs] of Object.entries(this.facial.entries)){
   const curve=this.facialCurves.get(name);if(!curve)continue;
   const v=evaluateSourceCurve({interpolation:curve.interpolation,keys:curve.keys},time);
   if(v===0)continue;used++;
   for(const a of attrs){
    const w=v*a.weight;
    if(a.jawOpen)jawOpen+=w;
    if(a.blinkScale)blinkScale+=w;
    // A negative product means the companion _Neg attribute carries this
    // direction. addPose only accepts non-negative weights.
    if(w>0)byPose.set(a.pose,(byPose.get(a.pose)??0)+w);else negativeSkipped++;
   }
  }
  for(const [name,w] of byPose){
   const pose=this.poseByName.get(name);if(!pose){missing++;continue;}
   const applied=w*blend;maxWeight=Math.max(maxWeight,applied);this.addPose(pose,applied);
  }
  this.lastFacial={time,used,poses:byPose.size,applied:byPose.size-missing,missing,maxWeight,negativeSkipped,jawOpen,blinkScale,blend};
 }
 apply(dt){
  if(this.playing&&dt>0){
   this.time+=dt*this.speed;this.faceTime+=dt*this.speed;this.seekBodyEnd=this.seekFaceEnd=false;this.dirty=true;
   // 非循环片段播完必须真的停下来：否则 time 越界后 displayTime 永远钳在末帧，
   // 播放开关看着是开的却毫无反应，只有拖进度条或从头播放能救。
   const limit=this.duration||this.faceDuration;
   if(!this.loop&&limit>0&&this.time>=limit){this.time=limit;this.faceTime=Math.min(this.faceTime,this.faceDuration||limit);this.playing=false;}
  }
  if(!this.dirty){this.updated=false;return false;}
  this.resetPose();const body=this.clips.get(this.body);
  if(body){const time=this.displayTime;for(let i=0;i<this.local.length;i++){const t=this.local[i];this.sample(body,time,i,t.p,t.q,t.s);}if(this.inPlace){const d=body.data;this.local[0].p.x=d[0]*.01;this.local[0].p.z=-d[1]*.01;}}
  const face=this.clips.get(this.face);
  if(face){
   const mask=this.face.startsWith('Pos_Look')?[...this.faceMask,9,10]:this.faceMask,time=this.displayFaceTime;
   for(const i of mask){const t=this.local[i];this.sample(face,time,i,this.tmpP,this.tmpQ,this.tmpS);t.p.lerp(this.tmpP,this.faceWeight);t.q.slerp(this.tmpQ,this.faceWeight).normalize();t.s.lerp(this.tmpS,this.faceWeight);}
  }
  this.lastAuthoredBlink=null;this.lastFacial=null;
  if(this.face==='authored_blink'){
   const raw=evaluateSourceCurve(this.blinkCurve,this.displayFaceTime),weight=Math.max(0,raw)*this.faceWeight;
   this.addPose(this.poseByName.get('EyeBlink'),weight);this.lastAuthoredBlink={time:this.displayFaceTime,rawValue:raw,appliedPositiveWeight:weight};
  }
  if(this.face==='authored_all')this.applyFacial(this.displayFaceTime,this.faceWeight);
  this.addPose(this.poseByName.get(this.pose),this.poseWeight);
  this.applyMorph();
  this.computeWorld();for(let i=0;i<this.skin.length;i++)this.skin[i].multiplyMatrices(this.world[i],this.inverseBind[i]);
  if(this.headIndex>=0)this.headDelta.setFromMatrix4(this.skin[this.headIndex]);this.skinVertices();this.dirty=false;this.updated=true;return true;
 }
 // ---- blend shapes ------------------------------------------------------
 // The game drives the face with morph targets, not bones: the mesh carries
 // the deltas and every AnimSequence carries float curves named exactly after
 // those targets, so the curve value is the blend weight.
 setMorph(data){
  if(!data){this.morph=null;this.morphP=null;this.morphN=null;return;}
  const view=new DataView(data.buffer),list=data.targets.targets,targets=[];
  for(const {name,count,offset} of list){
   const n=view.getInt32(offset,true);
   if(n!==count)throw Error('变形目标顶点数不一致：'+name);
   const ids=new Int32Array(n),pos=new Float32Array(n*3),nrm=new Float32Array(n*3);let o=offset+4;
   for(let i=0;i<n;i++){
    ids[i]=view.getInt32(o,true);o+=4;
    pos[i*3]=view.getFloat32(o,true);pos[i*3+1]=view.getFloat32(o+4,true);pos[i*3+2]=view.getFloat32(o+8,true);o+=12;
    nrm[i*3]=view.getFloat32(o,true);nrm[i*3+1]=view.getFloat32(o+4,true);nrm[i*3+2]=view.getFloat32(o+8,true);o+=12;
   }
   targets.push({name,count:n,ids,pos,nrm});
  }
  this.morph={targets,clips:data.curves.clips,index:new Map(targets.map((t,i)=>[t.name,i]))};
  this.morphP=new Float32Array(this.baseP);this.morphN=new Float32Array(this.baseN);
  this.morphWeights=new Float32Array(targets.length);this.morphEnabled=true;
  this.morphActive=0;this.morphMaxWeight=0;this.lastMorph=null;
 }
 morphApplyClip(name,time,weights,blend){
  const entry=this.morph?.clips[name];if(!entry)return 0;let used=0;
  for(const curveName in entry.curves){const index=this.morph.index.get(curveName);if(index===undefined)continue;
   const curve=entry.curves[curveName],raw=evaluateSourceCurve({interpolation:curve.interp,keys:curve.keys},time);
   // Blend weights stay in [0,1]; cubic tangents can overshoot past a key.
   const value=Math.max(0,Math.min(1,raw));
   weights[index]=blend>=1?value:weights[index]*(1-blend)+value*blend;used++;
  }return used;
 }
 applyMorph(){
  if(!this.morph||!this.morphEnabled){this.morphP=null;this.morphN=null;return;}
  if(!this.morphP)this.morphP=new Float32Array(this.baseP);
  if(!this.morphN)this.morphN=new Float32Array(this.baseN);
  this.morphWeights.fill(0);
  const usedBody=this.morphApplyClip(this.body,this.displayTime,this.morphWeights,1);
  const usedFace=this.morphApplyClip(this.face,this.displayFaceTime,this.morphWeights,this.faceWeight);
  const w=this.morphWeights,list=this.morph.targets,baseP=this.baseP,baseN=this.baseN,mp=this.morphP,mn=this.morphN;
  mp.set(baseP);mn.set(baseN);
  let active=0,maxWeight=0,peak='';
  for(let t=0;t<list.length;t++){
   const weight=w[t];if(weight<=0)continue;
   active++;if(weight>maxWeight){maxWeight=weight;peak=list[t].name;}
   const target=list[t],ids=target.ids,pos=target.pos,nrm=target.nrm,count=target.count;
   for(let k=0;k<count;k++){const v=ids[k]*3;
    mp[v]+=weight*pos[k*3];mp[v+1]+=weight*pos[k*3+1];mp[v+2]+=weight*pos[k*3+2];
    mn[v]+=weight*nrm[k*3];mn[v+1]+=weight*nrm[k*3+1];mn[v+2]+=weight*nrm[k*3+2];}
  }
  this.morphActive=active;this.morphMaxWeight=maxWeight;
  this.lastMorph={usedBody,usedFace,active,maxWeight,peak};
 }
 skinVertices(){
  const p=this.morphP??this.baseP,n=this.morphN??this.baseN,t=this.baseT,outP=this.positions,outN=this.normals,outT=this.tangents,ids=this.ids,weights=this.weights,k=this.influences;
  for(let v=0;v<outP.length/3;v++){
   const i=v*3,j=v*4,px=p[i],py=p[i+1],pz=p[i+2],nx=n[i],ny=n[i+1],nz=n[i+2],tx=t[j],ty=t[j+1],tz=t[j+2];let x=0,y=0,z=0,a=0,b=0,c=0,d=0,e=0,f=0;
   for(let s=0;s<k;s++){const w=weights[v*k+s];if(w===0)continue;const m=this.skin[ids[v*k+s]].elements;
    x+=(m[0]*px+m[4]*py+m[8]*pz+m[12])*w;y+=(m[1]*px+m[5]*py+m[9]*pz+m[13])*w;z+=(m[2]*px+m[6]*py+m[10]*pz+m[14])*w;
    a+=(m[0]*nx+m[4]*ny+m[8]*nz)*w;b+=(m[1]*nx+m[5]*ny+m[9]*nz)*w;c+=(m[2]*nx+m[6]*ny+m[10]*nz)*w;
    d+=(m[0]*tx+m[4]*ty+m[8]*tz)*w;e+=(m[1]*tx+m[5]*ty+m[9]*tz)*w;f+=(m[2]*tx+m[6]*ty+m[10]*tz)*w;
   }
   outP[i]=x;outP[i+1]=y;outP[i+2]=z;outN[i]=a;outN[i+1]=b;outN[i+2]=c;outT[j]=d;outT[j+1]=e;outT[j+2]=f;outT[j+3]=t[j+3];
  }
  for(const name of ['position','normal','tangent'])this.model.geometry.attributes[name].needsUpdate=true;
 }
 bindError(){
  let err=0;for(let i=0;i<this.skin.length;i++){const m=new THREE.Matrix4().multiplyMatrices(this.world[i],this.inverseBind[i]).elements;for(let j=0;j<16;j++)err=Math.max(err,Math.abs(m[j]-(j%5===0?1:0)));}return err;
 }
 summary(){return {body:this.body,face:this.face,pose:this.pose,time:this.time,faceTime:this.faceTime,playing:this.playing,speed:this.speed,inPlace:this.inPlace,duration:this.duration,faceDuration:this.faceDuration,authoredBlink:this.lastAuthoredBlink,facial:this.lastFacial,facialStats:this.facial?.stats??null,clipCount:this.clips.size,poseCount:this.poses.poses.length,bindError:this.referenceSkinError,morphTargets:this.morph?.targets.length??0,morph:this.lastMorph};}
}
