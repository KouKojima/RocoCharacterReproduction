import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {loadAsset,loadTextures,loadModel,loadMorph,loadGaze,loadFacial} from './assets.js';
import {makeMaterial,makeOutline,makePost,makeGround} from './materials.js';
import {loadNativeAnimation,evaluateSourceCurve} from './animation.js';

const $=id=>document.getElementById(id),canvas=$('viewport'),stage=$('stage');
const state={body:true,face:true,eyes:true,outline:true,morph:true,debug:0,outlineWidth:1,animateEyes:false,gaze:true,eyeSpeed:1,leftX:0,leftY:0,rightX:0,rightY:0,pupilScale:1,vertexControls:true,lightAzimuth:-35,lightElevation:38,sun:1,ambient:.65,shadow:.65,turntable:false,ground:true,lightSweep:false,animationClip:'World_Idle',faceClip:'none',poseName:'Reference',nativePlaying:true,nativeSpeed:1,nativeLoop:true,inPlace:true,faceWeight:1,poseWeight:1};
const defaults={...state};
const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});
renderer.setPixelRatio(Math.min(devicePixelRatio,1.7));renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
const scene=new THREE.Scene();scene.background=new THREE.Color(.019,.029,.032);
const camera=new THREE.PerspectiveCamera(33,1,.015,80);camera.position.set(2.25,1.45,-4.05);
const controls=new OrbitControls(camera,canvas);controls.target.set(0,.98,0);controls.enableDamping=true;controls.dampingFactor=.09;controls.minDistance=.25;controls.maxDistance=10;controls.maxPolarAngle=Math.PI*.93;controls.update();
const character=new THREE.Group();scene.add(character);const meshes=[],outlines=[],uniformSets=[];
const lightDir=new THREE.Vector3(),shadowCamera=new THREE.OrthographicCamera(-1.65,1.65,1.9,-1.9,.1,15);
const shadowTarget=new THREE.WebGLRenderTarget(1536,1536,{minFilter:THREE.NearestFilter,magFilter:THREE.NearestFilter,format:THREE.RGBAFormat,depthBuffer:true});
shadowTarget.depthTexture=new THREE.DepthTexture(1536,1536,THREE.UnsignedIntType);shadowTarget.depthTexture.minFilter=shadowTarget.depthTexture.magFilter=THREE.NearestFilter;
const shadowDepthMaterial=new THREE.MeshDepthMaterial({side:THREE.DoubleSide,polygonOffset:true,polygonOffsetFactor:3,polygonOffsetUnits:4});
const shared={uLightDir:{value:lightDir},uLightColor:{value:new THREE.Vector3(1,.975,.94)},uAmbientColor:{value:new THREE.Vector3(.59,.64,.69)},uShadowMap:{value:shadowTarget.depthTexture},uShadowMatrix:{value:new THREE.Matrix4()},uShadowStrength:{value:state.shadow},uViewport:{value:new THREE.Vector2()},uInverseViewProjection:{value:new THREE.Matrix4()},uDebug:{value:0},uVertexControls:{value:1},uOutlineWidth:{value:1},uBasisX:{value:new THREE.Vector3(1,0,0)},uBasisY:{value:new THREE.Vector3(0,0,-1)},uBasisZ:{value:new THREE.Vector3(0,1,0)},uCameraRight:{value:new THREE.Vector3()},uCameraForward:{value:new THREE.Vector3()},uViewRotation:{value:new THREE.Matrix3()},uDirectScale:{value:1},uAmbientStrength:{value:state.ambient},uAmbientDesaturation:{value:0},uAmbientScale:{value:1},uColorDesaturation:{value:0},uShadowBias:{value:0},uAmbientDarkAdd:{value:0},uRimEnabled:{value:1}};
const ground=makeGround(shared);scene.add(ground);const post=makePost(renderer);
let assets,model,materials,animator,eyeUniforms,baseEyeRows,loaded=false,shadowDirty=true,lastLight='',elapsed=0,paused=false,viewMode='full',lastRotation=0,gazeData=null,lastGaze=null,facialData=null;
const faceBasis={uBasisX:{value:new THREE.Vector3(1,0,0)},uBasisY:{value:new THREE.Vector3(0,0,-1)},uBasisZ:{value:new THREE.Vector3(0,1,0)}};
const matRows=rows=>Array.from({length:64},(_,i)=>new THREE.Vector4(...(rows[i]??[0,0,0,0])));

function textureName(instance,key){const ref=instance.texture[key];return ref?.ObjectPath?.split('/').pop().split('.')[0];}
function uniformsFor(kind,buffer,bindings){
 const u={...shared,uMat:{value:matRows(buffer.buffer)}};
 if(kind==='face'||kind==='eyes')Object.assign(u,faceBasis);
 if(kind==='eyes')u.uGazeOffset={value:new THREE.Vector4()};
 for(const name of ['uBase','uMask','uId','uFace','uMatcap','uHue','uRamp'])u[name]={value:assets[bindings[name]??'TestResMainTex01']};
 uniformSets.push(u);return u;
}
function sectionGeometry(source,section){
 const g=new THREE.BufferGeometry();for(const [name,attribute]of Object.entries(source.attributes))g.setAttribute(name,attribute);
 g.setIndex(source.index);g.setDrawRange(section.start,section.count);g.boundingBox=source.boundingBox;g.boundingSphere=source.boundingSphere;return g;
}
function lightUpdate(){
 const a=THREE.MathUtils.degToRad(state.lightAzimuth),e=THREE.MathUtils.degToRad(state.lightElevation);
 lightDir.set(Math.sin(a)*Math.cos(e),Math.sin(e),-Math.cos(a)*Math.cos(e)).normalize();
 shared.uLightColor.value.set(state.sun,state.sun*.975,state.sun*.94);shared.uAmbientStrength.value=state.ambient;shared.uShadowStrength.value=state.shadow;
 const key=[state.lightAzimuth,state.lightElevation].join(',');if(key!==lastLight){shadowDirty=true;lastLight=key;}
 shadowCamera.position.copy(lightDir).multiplyScalar(5).add(new THREE.Vector3(0,1,0));shadowCamera.lookAt(0,1,0);shadowCamera.updateMatrixWorld();
 const bias=new THREE.Matrix4().set(.5,0,0,.5,0,.5,0,.5,0,0,.5,.5,0,0,0,1);
 shared.uShadowMatrix.value.copy(bias).multiply(shadowCamera.projectionMatrix).multiply(shadowCamera.matrixWorldInverse);
}
function renderShadow(){
 if(!shadowDirty)return;
 const save=scene.background;scene.background=null;ground.visible=false;for(const m of outlines)m.visible=false;
 scene.overrideMaterial=shadowDepthMaterial;renderer.setRenderTarget(shadowTarget);renderer.setClearColor(0xffffff,1);renderer.clear();renderer.render(scene,shadowCamera);scene.overrideMaterial=null;renderer.setRenderTarget(null);scene.background=save;ground.visible=state.ground;syncVisibility();shadowDirty=false;
}
function syncVisibility(){
 for(const m of meshes)m.visible=state[m.userData.kind];
 for(const m of outlines)m.visible=state.outline&&state[m.userData.kind]&&state.debug===0&&state.outlineWidth>.001;
 ground.visible=state.ground;
 shared.uDebug.value=post.uniforms.uDebug.value=Number(state.debug);shared.uOutlineWidth.value=state.outlineWidth;shared.uVertexControls.value=state.vertexControls?1:0;
}
// The original per-clip ec_u/v_offset_* curves are sampled against the body
// clip's own timeline. Values are used verbatim; nothing here guesses a sign
// or a scale for MF_FacialAnimationUV (see docs/05).
function sampleGaze(){
 if(!gazeData||!animator||!state.gaze)return null;
 const clip=gazeData.clips?.[animator.body],curves=clip?.curves;
 const info={clip:animator.body,time:animator.displayTime,active:!!curves,channels:curves?Object.keys(curves).length:0};
 if(!curves)return info;
 const at=name=>{const c=curves[name];return c?evaluateSourceCurve({interpolation:c.interp,keys:c.keys},info.time):0;};
 info.uL=at('ec_u_offset_l');info.vL=at('ec_v_offset_l');info.uR=at('ec_u_offset_r');info.vR=at('ec_v_offset_r');
 return info;
}
let gazeNoteKey='';
function updateGazeNote(g){
 const el=$('gazeNote');if(!el)return;
 let text,key;
 if(!gazeData){text='此角色没有提取到原版注视曲线（旧提取布局），可用下方手动滑杆。';key='none';}
 else if(!state.gaze){text='原版注视曲线已关闭，可用手动滑杆或演示扫视。';key='off';}
 else if(!g?.active){text='当前动作「'+(g?.clip??'—')+'」未带注视曲线；该角色有 '+Object.keys(gazeData.clips).length+' 个动作带数据。';key=(g?.clip??'')+'|none';}
 else{text='原版注视 · '+g.channels+' 通道 · 原始值直接叠加 UV（材质函数符号/缩放未逐帧对拍）。';key=g.clip+'|'+g.channels;}
 if(key!==gazeNoteKey){el.textContent=text;gazeNoteKey=key;}
}
function updateEyes(t){
 if(!eyeUniforms)return;
 const gaze=sampleGaze();lastGaze=gaze;updateGazeNote(gaze);
 if(eyeUniforms.uGazeOffset){
  const v=eyeUniforms.uGazeOffset.value;
  if(gaze?.active)v.set(gaze.uL,gaze.vL,gaze.uR,gaze.vR);else v.set(0,0,0,0);
 }
 const rows=eyeUniforms.uMat.value,b=baseEyeRows;
 let lx=state.leftX,ly=state.leftY,rx=state.rightX,ry=state.rightY;
 if(state.animateEyes){
  // Demonstration timing; UV transforms and independent per-eye controls are
  // the original material mechanism. No invented skeletal motion is applied.
  const x=.036*Math.sin(t*.7*state.eyeSpeed)+.012*Math.sin(t*1.93*state.eyeSpeed);
  const y=.023*Math.sin(t*.46*state.eyeSpeed+.65);
  lx+=x;rx+=x;ly+=y;ry+=y;
 }
 const scale=1/state.pupilScale-1;
 rows[6].set(b[6][0]+scale,b[6][1]+scale,b[6][2]-rx,b[6][3]+ry);
 rows[7].set(b[7][0]+scale,b[7][1]+scale,b[7][2]+lx,b[7][3]+ly);
}
function resize(){
 const rect=stage.getBoundingClientRect();camera.aspect=rect.width/rect.height;camera.updateProjectionMatrix();renderer.setSize(rect.width,rect.height,false);const size=new THREE.Vector2();renderer.getDrawingBufferSize(size);post.resize(size.x,size.y);shared.uViewport.value.copy(size);shadowDirty=true;
}
new ResizeObserver(resize).observe(stage);
function setView(mode){
 viewMode=mode;character.rotation.y=0;state.turntable=false;$('turntable').checked=false;
 if(mode==='full'){controls.target.set(0,.98,0);camera.position.set(2.25,1.45,-4.05);}
 if(mode==='face'){controls.target.set(0,1.5,-.06);camera.position.set(.43,1.51,-1.32);}
 if(mode==='eyes'){controls.target.set(0,1.495,-.101);camera.position.set(.038,1.5,-.61);}
 controls.update();for(const b of document.querySelectorAll('[data-view]'))b.classList.toggle('active',b.dataset.view===mode);shadowDirty=true;
}
function displayValue(key){
 const out=$(key+'-out');if(!out)return;let value=state[key];
 out.value=out.textContent=(key.startsWith('light')?Math.round(value)+'°':Number(value).toFixed(2)+(['outlineWidth','eyeSpeed','pupilScale'].includes(key)?'×':''));
}
function setState(patch){
 Object.assign(state,patch);for(const [key,value]of Object.entries(patch)){const el=$(key);if(el){if(el.type==='checkbox')el.checked=!!value;else el.value=value;}displayValue(key);}
 if(animator){
  if('animationClip'in patch)animator.setBody(patch.animationClip);
  if('faceClip'in patch)animator.setFace(patch.faceClip);
  if('poseName'in patch)animator.setPose(patch.poseName);
  animator.playing=state.nativePlaying;animator.speed=state.nativeSpeed;animator.loop=state.nativeLoop;animator.inPlace=state.inPlace;animator.poseWeight=state.poseWeight;animator.faceWeight=state.faceWeight;animator.morphEnabled=state.morph;animator.dirty=true;
  if(state.nativePlaying&&animator.atEnd)animator.seek(0);
 }
 lightUpdate();syncVisibility();shadowDirty=true;
}
for(const key of Object.keys(state)){
 const el=$(key);if(!el)continue;
 el.addEventListener('input',()=>{
  const value=el.type==='checkbox'?el.checked:el.type==='range'||key==='debug'?Number(el.value):el.value;
  const patch={[key]:value};
  if(['leftX','leftY','rightX','rightY'].includes(key)&&state.animateEyes)patch.animateEyes=false;
  // Synthetic sweep and original per-clip curves are alternative timing
  // sources; enabling either one disables the other to avoid double motion.
  if(key==='animateEyes'&&value)patch.gaze=false;
  if(key==='gaze'&&value)patch.animateEyes=false;
  setState(patch);
 });displayValue(key);
}
for(const b of document.querySelectorAll('[data-view]'))b.onclick=()=>setView(b.dataset.view);
$('reset').onclick=()=>{setState(defaults);elapsed=0;setView('full');};
$('lightSweep').onclick=()=>{state.lightSweep=!state.lightSweep;$('lightSweep').classList.toggle('active',state.lightSweep);};
$('shot').onclick=()=>{drawFrame(0);const a=document.createElement('a');a.href=canvas.toDataURL('image/png');a.download='洛克王国-原版人物-'+viewMode+'.png';a.click();};
// 只注册一次：放进 populateAnimationControls 会随每次切角色叠加一份，
// 拖动一次进度条就重复 seek + 整帧重绘 N 次。
$('animationTimeline').addEventListener('input',()=>{if(!animator)return;animator.seek(Number($('animationTimeline').value)*animator.duration);setState({nativePlaying:false});drawFrame(0);});
$('faceTimeline').addEventListener('input',()=>{if(!animator)return;animator.seekFace(Number($('faceTimeline').value)*animator.faceDuration);setState({nativePlaying:false});drawFrame(0);});
$('restartAnimation').onclick=()=>{if(!animator)return;animator.seek(0);setState({nativePlaying:true});};
let last=performance.now(),fpsTimer=0,frames=0,frameErrorLogged=false;
function drawFrame(dt){
 if(!loaded)return;
 if(!paused)elapsed+=dt;
 if(animator?.apply(paused?0:dt))shadowDirty=true;
 if(state.turntable&&!paused)character.rotation.y+=dt*.24;
 if(state.lightSweep&&!paused){state.lightAzimuth=(elapsed*16)%360-180;$('lightAzimuth').value=state.lightAzimuth;displayValue('lightAzimuth');}
 if(character.rotation.y!==lastRotation){shadowDirty=true;lastRotation=character.rotation.y;}
 character.updateMatrixWorld();shared.uBasisX.value.set(1,0,0).transformDirection(character.matrixWorld);shared.uBasisY.value.set(0,0,-1).transformDirection(character.matrixWorld);shared.uBasisZ.value.set(0,1,0).transformDirection(character.matrixWorld);
 for(const [key,v]of [['uBasisX',[1,0,0]],['uBasisY',[0,0,-1]],['uBasisZ',[0,1,0]]]){faceBasis[key].value.set(...v);if(animator)faceBasis[key].value.applyMatrix3(animator.headDelta);faceBasis[key].value.transformDirection(character.matrixWorld);}
 controls.update();camera.updateMatrixWorld();lightUpdate();updateEyes(elapsed);
 shared.uCameraRight.value.setFromMatrixColumn(camera.matrixWorld,0);camera.getWorldDirection(shared.uCameraForward.value);
 const rot=new THREE.Matrix4().makeScale(1,1,-1).multiply(camera.matrixWorldInverse);shared.uViewRotation.value.setFromMatrix4(rot);
 shared.uInverseViewProjection.value.copy(camera.projectionMatrix).multiply(camera.matrixWorldInverse).invert();renderShadow();post.render(scene,camera);
 if(animator&&animator.playing!==state.nativePlaying){state.nativePlaying=animator.playing;$('nativePlaying').checked=animator.playing;}
 if(animator){const d=animator.duration,t=animator.displayTime,fd=animator.faceDuration,ft=animator.displayFaceTime;$('animationTimeline').value=d?t/d:0;$('animationTime').textContent=t.toFixed(2)+' / '+d.toFixed(2)+' s';$('nativeSource').textContent=animator.body==='reference'?'原版参考姿势':animator.body;$('faceTimeline').disabled=!fd;$('faceTimeline').value=fd?ft/fd:0;$('faceTime-out').textContent=ft.toFixed(2)+' / '+fd.toFixed(2)+' s';const note=$('authoredNote');note.classList.toggle('hidden',animator.face!=='authored_blink'&&animator.face!=='authored_all');
  if(animator.face==='authored_all'){
   const f=animator.lastFacial,s=animator.facial?.stats;
   note.textContent='原版 controllerConfig 多通道：'+(f?'本次施加 '+f.applied+' 个 pose，最大权重 '+f.maxWeight.toFixed(3):'未施加')+
    '；jawOpen/blinkScale 通道未接入。'+(s&&s.missingPoses?' 本角色缺 '+s.missingPoses+' 个 pose 增量（无 PoseAsset），映射表仅作留档。':'');
  }else note.textContent='使用原版 8.725 秒样例的 EyeBlink 曲线与原姿势；负值不施加闭眼，仅演示这一通道，未模拟整套口型混合。';}
}
function tick(now){
 // 必须先排下一帧：drawFrame 抛异常会让循环永久停摆，之后播放按钮全部失效，
 // 只有进度条还能动（它的处理函数同步调 drawFrame(0)）。
 requestAnimationFrame(tick);
 const dt=(now-last)/1000;last=now;
 try{drawFrame(dt);}catch(error){if(!frameErrorLogged){frameErrorLogged=true;console.error('渲染帧异常，循环继续运行',error);}}
 // FPS 用真实墙钟 dt；钳制过的 dt 会把实际 1 FPS 报成 20 FPS，掩盖掉帧。
 frames++;fpsTimer+=dt;if(fpsTimer>=1){$('frame-status').textContent=Math.round(frames/fpsTimer)+' FPS · WebGL 2';fpsTimer=0;frames=0;}
}
// 动画按真实时间推进，切回标签页时重置基准，避免一次性跳过整段隐藏时长。
document.addEventListener('visibilitychange',()=>{if(!document.hidden)last=performance.now();});
let characters=[],currentChar=null;
const animationControlIds=['animationClip','faceClip','poseName','animationTimeline','faceTimeline','restartAnimation','nativePlaying','nativeSpeed','nativeLoop','inPlace','faceWeight','poseWeight','morph'];
async function disposeCharacter(){
 for(const m of meshes){character.remove(m);m.geometry?.dispose?.();m.material?.dispose?.();}
 for(const o of outlines){character.remove(o);o.geometry?.dispose?.();o.material?.dispose?.();}
 if(assets)for(const t of Object.values(assets))t?.dispose?.();
 meshes.length=0;outlines.length=0;uniformSets.length=0;
 animator=null;eyeUniforms=null;baseEyeRows=null;gazeData=null;lastGaze=null;gazeNoteKey='';facialData=null;
}
async function loadCharacter(entry){
 await disposeCharacter();
 const root='assets/'+entry.dir+'/';
 const [textures,loadedModel,loadedMaterials,loadedMorph,loadedGaze,loadedFacial]=await Promise.all([loadTextures(root),loadModel(root),loadAsset(root+'materials.json',true),loadMorph(root),loadGaze(root),loadFacial(root)]);
 assets=textures;model=loadedModel;materials=loadedMaterials;gazeData=loadedGaze;facialData=loadedFacial;
 if(materials.hasAnimation){
  for(const id of animationControlIds)if($(id))$(id).disabled=false;
  animator=await loadNativeAnimation(model,root+'animation/');
  animator.setMorph(loadedMorph);
  animator.setFacial(facialData);
  animator.morphEnabled=state.morph;
  if(animator.clips&&!animator.clips.has(animator.body)){const first=[...animator.clips.values()].find(c=>c.group==='body')||[...animator.clips.values()][0];if(first)animator.body=first.name;}
  populateAnimationControls();
  // populateAnimationControls only rewrites the dropdowns; the animator still
  // holds its construction defaults, so align it with the state the UI now
  // shows or the two disagree after a character switch.
  animator.setBody(state.animationClip);animator.setFace(state.faceClip);animator.setPose(state.poseName);
  animator.playing=state.nativePlaying;animator.speed=state.nativeSpeed;animator.loop=state.nativeLoop;animator.inPlace=state.inPlace;animator.poseWeight=state.poseWeight;animator.faceWeight=state.faceWeight;animator.morphEnabled=state.morph;animator.dirty=true;
 }else{for(const id of animationControlIds)if($(id))$(id).disabled=true;$('animationClip').innerHTML='<option>未提取动作 · 静态模式</option>';$('animationTime').textContent='静态参考姿势';$('nativeSource').textContent='未载入动作数据';}
 const defs=materials.defs;
 const mats={};
 const surfaceKinds=['body','im','face','eyes'].filter(k=>k==='im'?!!materials.buffers.im:true);
 for(const kind of surfaceKinds){const u=uniformsFor(kind,materials.buffers[kind],defs[kind]);mats[kind]=makeMaterial(kind,u);if(kind==='eyes'){eyeUniforms=u;baseEyeRows=materials.buffers.eyes.buffer;}}
 const outlineBody=makeOutline(uniformsFor('outline',materials.buffers.outline,defs.outline));
 const outlineFace=makeOutline(uniformsFor('faceOutline',materials.buffers.faceOutline,defs.faceOutline));
 const kinds=materials.sectionKinds||{};
 for(const section of model.metadata.sections){
  const kind=kinds[section.section]??kinds[section.materialIndex]??'body';
  const g=sectionGeometry(model.geometry,section),mesh=new THREE.Mesh(g,mats[kind]||mats.body);mesh.userData.kind=(kind==='body2'||kind==='im')?'body':kind;mesh.frustumCulled=false;mesh.renderOrder=2;character.add(mesh);meshes.push(mesh);
  const meshKind=mesh.userData.kind;
  if(meshKind!=='eyes'){const line=new THREE.Mesh(g,meshKind==='face'?outlineFace:outlineBody);line.userData.kind=meshKind;line.frustumCulled=false;line.renderOrder=1;character.add(line);outlines.push(line);}
 }
 currentChar=entry;elapsed=0;shadowDirty=true;
 $('scene-name').textContent=entry.label??entry.id;
 $('scene-stats').textContent=entry.stats??'';
 loaded=true;resize();lightUpdate();syncVisibility();updateEyes(0);drawFrame(0);
 $('live-status').textContent=animator?'原版动作 · 骨骼表情 · 独立材质':'静态参考姿势 · 独立材质';
}
async function init(){
 try{
  characters=await loadAsset('assets/characters.json',true);
  const sel=$('characterSelect');sel.innerHTML='';
  for(const c of characters){const o=document.createElement('option');o.value=c.id;o.textContent=c.label??c.id;sel.appendChild(o);}
  sel.onchange=async()=>{
   const entry=characters.find(c=>c.id===sel.value);if(!entry)return;
   $('loading').classList.remove('hidden');$('loading').style.opacity='1';$('load-text').textContent='正在载入 '+(entry.label??entry.id);
   try{await loadCharacter(entry);$('loading').style.opacity='0';setTimeout(()=>$('loading').classList.add('hidden'),300);}
   catch(error){console.error(error);$('load-text').textContent='载入失败：'+error.message;$('load-text').classList.add('error');}
  };
  await loadCharacter(characters[0]);
  $('loading').style.opacity='0';setTimeout(()=>$('loading').classList.add('hidden'),300);
  window.preview={state,renderer,scene,camera,controls,meshes,outlines,uniforms:shared,eyeUniforms,setState,setView,render:()=>drawFrame(0),pause:(v=true)=>{paused=v;},setTime:t=>{elapsed=t;animator?.seek(t);updateEyes(t);drawFrame(0);},get time(){return elapsed;},get view(){return viewMode;},characters,get character(){return currentChar;},get materials(){return materials;},get gaze(){return lastGaze;},get gazeData(){return gazeData;},get facialData(){return facialData;},get animator(){return animator;},get model(){return model;},switchCharacter:id=>{sel.value=id;sel.onchange();},ready:true};
  last=performance.now();requestAnimationFrame(tick);
 }catch(error){console.error(error);$('load-text').textContent='载入失败：'+error.message;$('load-text').classList.add('error');$('loading').querySelector('small').textContent='请按 character/START_HERE.txt 提取本机数据、构建并启动预览';}
}
function populateAnimationControls(){
 const body=$('animationClip'),face=$('faceClip'),poses=$('poseName');body.innerHTML='<option value="reference">参考姿势</option>';face.innerHTML='<option value="none">跟随身体动作</option>';
 for(const meta of animator.manifest.clips){const option=document.createElement('option');option.value=meta.name;option.textContent=meta.label+' · '+meta.name;(meta.group==='body'?body:face).appendChild(option);}
 const sample=document.createElement('option');sample.value='authored_blink';sample.textContent='原曲线眨眼样例 · TestData（仅 EyeBlink）';
 // The authored curve can only drive the face when the character owns the
 // matching skeletal pose; without a PoseAsset there is nothing to apply.
 if(animator.poseByName.has('EyeBlink'))face.appendChild(sample);
 if(facialData&&animator.poses.poses.length>1){
  const all=document.createElement('option');all.value='authored_all';
  all.textContent='原曲线全通道 · controllerConfig（'+facialData.stats.availablePoses+' 个 pose 可用）';
  face.appendChild(all);
 }
 const labels={Reference:'无附加姿势',EyeBlink:'闭眼 / EyeBlink',EyeBlink_Neg:'睁眼 / EyeBlink_Neg',LipTogether:'合唇 / LipTogether',LipTogether_Neg:'合唇反向 / LipTogether_Neg',BrowUp:'扬眉 / BrowUp',BrowDown:'压眉 / BrowDown'};
 for(const pose of animator.poses.poses){const option=document.createElement('option');option.value=pose.name;option.textContent=labels[pose.name]??pose.name;poses.appendChild(option);}
 body.value=state.animationClip;face.value=state.faceClip;poses.value=state.poseName;
 if(![...body.options].some(o=>o.value===state.animationClip)){const first=[...body.options].find(o=>o.value!=='reference');if(first){body.value=first.value;state.animationClip=first.value;}}
 if(![...face.options].some(o=>o.value===state.faceClip)){face.value='none';state.faceClip='none';}
 if(![...poses.options].some(o=>o.value===state.poseName)){const first=[...poses.options][0];if(first){poses.value=first.value;state.poseName=first.value;}}
}
init();
