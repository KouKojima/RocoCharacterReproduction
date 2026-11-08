import * as THREE from 'three';
import bodySource from '../body-face-port.glsl';
import outlineSource from '../outline-port.glsl';

const attributes=`
precision highp float;precision highp int;
uniform mat4 modelMatrix,viewMatrix,projectionMatrix;
in vec3 position,normal;in vec4 tangent,color;in vec2 uv,uv1;
out vec3 vWorldPosition,vNormal;out vec4 vTangent,vColor;out vec2 vUv,vUv1;
void attributesToWorld(){
 vWorldPosition=(modelMatrix*vec4(position,1.)).xyz;
 vNormal=mat3(modelMatrix)*normal;
 vTangent=vec4(mat3(modelMatrix)*tangent.xyz,tangent.w);
 vColor=color;vUv=uv;vUv1=uv1;
}
`;
const vertex=attributes+`void main(){attributesToWorld();gl_Position=projectionMatrix*viewMatrix*vec4(vWorldPosition,1.);}`;
const fragmentHeader=`
precision highp float;precision highp int;
#define texture2D texture
in vec3 vWorldPosition,vNormal;in vec4 vTangent,vColor;in vec2 vUv,vUv1;
out vec4 outColor;
uniform vec3 cameraPosition,uLightDir,uLightColor,uAmbientColor;
uniform vec4 uMat[64];uniform sampler2D uBase,uMask,uId,uFace,uMatcap;
uniform int uDebug;uniform float uVertexControls;uniform vec4 uGazeOffset;
uniform sampler2D uShadowMap;uniform mat4 uShadowMatrix;uniform float uShadowStrength;
float uShadow;
float worldShadow(vec3 p){
 vec3 n=normalize(vNormal);float slope=1.-max(dot(n,normalize(uLightDir)),0.);
 vec4 q=uShadowMatrix*vec4(p+n*.003,1.);vec3 c=q.xyz/q.w;
 if(c.x<0.||c.x>1.||c.y<0.||c.y>1.||c.z>1.||c.z<0.)return 1.;
 float sum=0.;float bias=.0015+.001*slope;
 for(int y=-1;y<=1;y++)for(int x=-1;x<=1;x++)sum+=step(c.z-bias,texture(uShadowMap,c.xy+vec2(float(x),float(y))/1536.).r);
 return mix(1.,sum/9.,uShadowStrength);
}
`;
// Source data is uploaded using native sRGB texture formats, so the GPU
// performs decode before filtering, exactly as for the original texture.
const bodyGLSL=bodySource.replace(/vec3 npcSRGB\(vec3 x\)\{[^}]*\}/,'vec3 npcSRGB(vec3 x){return x;}');

const eyeGLSL=`
vec2 eyeUV(){
 float chooseR=step(vUv.x,.5);
 vec4 controls=mix(uMat[7].xwyz,uMat[6].xwyz,chooseR);
 vec2 p=fract(vUv*vec2(2.,1.))-.5;
 // Original per-clip ec_u/v_offset_* curves are added as raw UV offsets to
 // their own eye. The sliders keep their mirrored sign convention; the original
 // curves do not go through it (their left/right values are near-identical).
 vec2 gaze=uGazeOffset.xy+chooseR*(uGazeOffset.zw-uGazeOffset.xy);
 return p*(1.+controls.xz)+.5-vec2(controls.w*uMat[28].x,controls.y)+gaze;
}
vec3 eyeBase(){
 vec4 pupil=texture(uBase,eyeUV());
 vec2 c=mix(vec2(1.),vColor.rg,uVertexControls);
 float t=clamp((c.x-uMat[29].y)/max(1.-uMat[29].y,.00001),0.,1.);t=t*t*(3.-2.*t);
 float specMask=1.-c.y;
 vec3 tint=mix(uMat[14].rgb,uMat[13].rgb*clamp(c.x-specMask,0.,1.),t);
 return npcInverseTone(pupil.rgb)*tint+uMat[16].rgb*specMask;
}
vec3 eyeSurface(){
 vec3 base=npcDesaturate(eyeBase());
 float amount=npcEyeAmount(uMat[18].x,uMat[18].y);
 // EmitterIntensity is zero in the original sampled material. Its inactive
 // UV3 emission-mask path is not substituted with the smooth-normal UV1.
 return npcCommonLight(base,amount,true)*uMat[25].rgb;
}
`;
export function makeMaterial(kind,uniforms){
 // The second body slot ("im") runs the same object pixel program as the body,
 // only with its own material instance, textures and constant buffer.
 const isBody=kind==='body'||kind==='im';
 const surface=isBody?'npcBodySurface()':kind==='face'?'npcFaceSurface()':'eyeSurface()';
 const debugBase=kind==='eyes'?'eyeBase()':'npcBaseSample()';
 const debugNormal=isBody?'npcNormal(texture(uMask,vUv))':'normalize(vNormal)';
 const debugID=kind==='eyes'?'vec3(fract(vUv*vec2(2.,1.)),0.)':'texture(uId,vUv).rgb';
 const debugFace=kind==='face'?'vec3(texture(uFace,vUv).r)':kind==='eyes'?'vec3(vColor.r,vColor.g,0.)':'vec3(texture(uMask,vUv).b)';
 const main=`void main(){
 uShadow=worldShadow(vWorldPosition);
 vec3 c=${surface};
 if(uDebug==1)c=${debugBase};
 if(uDebug==2)c=vColor.rgb;
 if(uDebug==3)c=${debugNormal}*.5+.5;
 if(uDebug==4)c=${debugID};
 if(uDebug==5)c=${debugFace};
 outColor=vec4(max(c,vec3(0.)),1.);
 }`;
 const material=new THREE.RawShaderMaterial({name:'NRC '+kind,uniforms,vertexShader:vertex,fragmentShader:fragmentHeader+bodyGLSL+eyeGLSL+main,glslVersion:THREE.GLSL3,side:THREE.FrontSide,toneMapped:false});
 return material;
}

export function makeOutline(uniforms){
 const vs=attributes+`
 uniform vec4 uMat[64];uniform vec3 cameraPosition;uniform vec2 uViewport;
 uniform mat4 uInverseViewProjection;uniform float uOutlineWidth;
 `+outlineSource+`
 void main(){
 attributesToWorld();
 vec3 smoothN=nrcOutlineSmoothNormal(vNormal,vTangent,vUv1,true);
 vec4 params=vec4(uMat[9].w,uMat[10].y,uMat[10].z,uMat[10].w);
 params.x*=uOutlineWidth;params.z*=max(uOutlineWidth,.001);
 vec3 offset=vec3(uMat[7].x,uMat[7].z,-uMat[7].y)*.01;
 vec3 p=nrcOutlineWorldPosition(vWorldPosition,smoothN,vColor,uViewport,cameraPosition,viewMatrix,projectionMatrix,uInverseViewProjection,params,uMat[10].x,uViewport.y/uViewport.x,offset);
 gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);
 }`;
 const fs=`precision highp float;precision highp int;
 in vec3 vWorldPosition,vNormal;in vec4 vTangent,vColor;in vec2 vUv,vUv1;out vec4 outColor;
 uniform vec4 uMat[64];uniform sampler2D uBase,uId,uHue;
 `+outlineSource+`
 void main(){
 vec3 base=textureLod(uBase,vUv,4.).rgb;
 float hue=texture(uHue,nrcOutlineHueUV(base)).r;
 vec3 c=nrcOutlineBaseColor(texture(uId,vUv).r,base,hue,true,uMat[2].rgb,vec4(uMat[4].rgb,uMat[8].z),uMat[8].w,vec4(uMat[5].rgb,uMat[9].x));
 outColor=vec4(max(c,vec3(0.)),1.);
 }`;
 return new THREE.RawShaderMaterial({name:'NRC original outline',uniforms,vertexShader:vs,fragmentShader:fs,glslVersion:THREE.GLSL3,side:THREE.BackSide,toneMapped:false});
}

export function makePost(renderer){
 const target=new THREE.WebGLRenderTarget(1,1,{type:THREE.HalfFloatType,format:THREE.RGBAFormat,depthBuffer:true});
 const uniforms={uImage:{value:target.texture},uDebug:{value:0}};
 const material=new THREE.RawShaderMaterial({uniforms,glslVersion:THREE.GLSL3,depthTest:false,depthWrite:false,toneMapped:false,
 vertexShader:'precision highp float;in vec3 position;out vec2 vUV;void main(){vUV=position.xy*.5+.5;gl_Position=vec4(position.xy,0.,1.);}',
 fragmentShader:`precision highp float;uniform sampler2D uImage;uniform int uDebug;in vec2 vUV;out vec4 outColor;
 vec3 outputSRGB(vec3 c){c=max(c,vec3(.000061));return min(c*12.92,1.055*pow(max(c,vec3(.003131)),vec3(.416667))-.055);}
 void main(){vec3 c=max(texture(uImage,vUV).rgb,vec3(0.));if(uDebug<=1){c=c*(1.36*c+.047)/(c*(.93*c+.56)+.14);c=outputSRGB(c);}outColor=vec4(clamp(c,0.,1.),1.);}`});
 const scene=new THREE.Scene(),camera=new THREE.Camera();scene.add(new THREE.Mesh(new THREE.PlaneGeometry(2,2),material));
 return {target,uniforms,resize(w,h){target.setSize(w,h);},render(world,view){renderer.setRenderTarget(target);renderer.render(world,view);renderer.setRenderTarget(null);renderer.render(scene,camera);}};
}

export function makeGround(shared){
 const uniforms={...shared,uGroundColor:{value:new THREE.Color(.09,.117,.112)}};
 const material=new THREE.RawShaderMaterial({uniforms,glslVersion:THREE.GLSL3,toneMapped:false,side:THREE.DoubleSide,
 vertexShader:'precision highp float;uniform mat4 modelMatrix,viewMatrix,projectionMatrix;in vec3 position;out vec3 vWorldPosition;void main(){vec4 p=modelMatrix*vec4(position,1.);vWorldPosition=p.xyz;gl_Position=projectionMatrix*viewMatrix*p;}',
 fragmentShader:`precision highp float;in vec3 vWorldPosition;out vec4 outColor;uniform sampler2D uShadowMap;uniform mat4 uShadowMatrix;uniform float uShadowStrength;uniform vec3 uGroundColor;
 void main(){vec4 q=uShadowMatrix*vec4(vWorldPosition,1.);vec3 c=q.xyz/q.w;float s=0.;for(int y=-1;y<=1;y++)for(int x=-1;x<=1;x++)s+=step(c.z-.0005,texture(uShadowMap,c.xy+vec2(float(x),float(y))/1536.).r);s=mix(1.,s/9.,uShadowStrength);float fade=smoothstep(2.6,.7,length(vWorldPosition.xz));outColor=vec4(uGroundColor*mix(.55,1.,s),fade);}`,
 transparent:true,depthWrite:false});
 const mesh=new THREE.Mesh(new THREE.PlaneGeometry(14,14),material);mesh.rotation.x=-Math.PI/2;mesh.position.y=-.006;mesh.renderOrder=-1;return mesh;
}
