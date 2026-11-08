// Recovered material kernel for NPC_00401. Not original source.
// Body: FF2C5356, PS fb556f9017a383e6e995014526b91d2a681ec9b2.
// Face: BB257F24, PS fca52541baeaff6914775dbf81e98de3eaaa1640.
// Caller supplies uMat[64], uBase/uMask/uId/uFace/uMatcap,
// vWorldPosition/vNormal/vTangent/vUv/vUv1/vColor, cameraPosition,
// uLightDir/uLightColor/uAmbientColor, and mutable global float uShadow.
// Coordinates are preview coordinates (UE x,z,-y); normals and basis transformed.
// Color samplers contain raw PNG values with NoColorSpace; explicit SRGB decode.
// Output is scene-linear; caller applies original tone curve and output encoding.

uniform vec3 uBasisX, uBasisY, uBasisZ;
uniform vec3 uCameraRight, uCameraForward;
uniform mat3 uViewRotation;
uniform float uDirectScale;
uniform float uAmbientStrength, uAmbientDesaturation, uAmbientScale;
uniform float uColorDesaturation, uShadowBias, uAmbientDarkAdd;
uniform float uRimEnabled;

float npcSat(float x){return clamp(x,0.0,1.0);}
float npcSmooth(float t){t=npcSat(t);return t*t*(3.0-2.0*t);}
vec3 npcSRGB(vec3 x){
  #ifdef NRC_HARDWARE_SRGB
    return x;
  #else
    return mix(x/12.92,pow((x+0.055)/1.055,vec3(2.4)),step(vec3(0.04045),x));
  #endif
}
vec3 npcInverseTone(vec3 c){return (vec3(0.047)-0.56*c-sqrt(max(vec3(0.0),-0.2072*c*c+0.70896*c+0.002209)))/(1.86*c-2.72);}
vec3 npcBaseSample(){return npcInverseTone(npcSRGB(texture2D(uBase,vUv).rgb));}
vec3 npcDesaturate(vec3 c){return mix(c,vec3(dot(c,vec3(.3,.59,.11))),uColorDesaturation);}

// This multiplier is common to body, face, and eyes. uShadow includes whatever
// original shadow policy is represented by the caller's shadow input.
float npcMainAmount(float materialAmount){
  float lum=dot(uLightColor,vec3(.375,.5,.125));
  return materialAmount*npcSat(2.0*lum)*npcSat(uShadow+uShadowBias)*npcSat(uDirectScale);
}

// Exact simple response used after the recovered eye base-color input.
// The body/face low variants use constant .92 instead of 3-2*amount.
vec3 npcCommonLight(vec3 base,float amount,bool eye){
  vec3 tint=mix(uAmbientColor*(eye?(3.0-2.0*amount):.92),vec3(1.0),npcSat(uAmbientDesaturation));
  float darkAdd=min(uAmbientDarkAdd,0.0);
  return base*amount*(uLightColor+darkAdd)+base*darkAdd
       +base*npcSat(uAmbientStrength)*uAmbientScale*tint;
}

// Eye lighting uses the primitive's local +Y direction, not the eye surface
// normal. Optional original primitive custom basis override is represented by
// updating uBasisY on the CPU, rather than substituting the geometric normal.
float npcEyeAmount(float threshold,float softEdge){
  float n=dot(normalize(uBasisY),normalize(uLightDir));
  float h=.5*n+.5;
  float k=min(.5*(h+.55),1.0);
  float f=k+h*(.5*(h+.55)-k);
  float t=npcSat((f-threshold)/(softEdge*.1));
  if(t>.95)t=1.0;
  return npcMainAmount(t);
}

vec3 npcNormal(vec4 packed){
  vec2 n=packed.rg*2.0-1.0;
  // The original interpolated tangent frame is used without separately
  // renormalizing T/N. Only the resulting mapped normal is normalized.
  vec3 T=vTangent.xyz,N=vNormal;
  vec3 B=cross(N,T)*vTangent.w;
  return normalize(T*n.x+B*n.y+N*sqrt(1.0-min(dot(n,n),1.0)));
}
float npcRegion(vec3 id){return floor(min((1.0-id.r)*5.0+1.0,5.0));}
vec3 npcSpecParameters(float region,bool face){
  vec3 s=face?vec3(.35,.001,.5):uMat[33].xyz;
  if(region==2.0)s=face?uMat[21].xyz:uMat[17].xyz;
  if(region==3.0)s=face?uMat[24].xyz:uMat[20].xyz;
  if(region==4.0)s=face?uMat[27].xyz:uMat[23].xyz;
  if(region==5.0)s=face?uMat[30].xyz:uMat[26].xyz;
  return s;
}
float npcSpecKernel(float noH,float mask,vec3 p){
  float a=p.x*p.x;
  float d=a/((a*noH)*(a*noH)+1.0-noH*noH);
  d=min(d*d,2048.0);
  float k=.25*p.x+.25;
  float x=d*k;
  float band=npcSat((npcSat((x+mask)*.5)-(.49-p.z))/(2.0*p.z));
  return (npcSat(x)+p.z*p.z*(x-npcSat(x)))*band*mask*p.y;
}
vec3 npcRampBase(vec3 base,float amount,float ao,float isSkin,
                 float rampCoordinate,bool face,float matIdR){
  vec3 tint=face?uMat[11].rgb:mix(vec3(1.0),uMat[11].rgb,isSkin);
  float alpha=face?npcSat(uMat[11].a):npcSat(isSkin*uMat[11].a);
  float position=face?uMat[12].x:mix(.55,.5,isSkin);
  float width=face?uMat[12].y:mix(uMat[13].y,.25,isSkin);
  float saturation=face?uMat[12].z:mix(uMat[13].z,2.5,isSkin);
  float intensity=face?uMat[12].w:mix(uMat[13].w,isSkin*uMat[11].a*uMat[13].w,isSkin);
  float gray=dot(base,vec3(.32,.30,.40));
  vec3 saturated=vec3(gray)+(base-gray)*saturation;
  vec3 target=mix(saturated*.8,tint,alpha);
  float strength=amount*intensity*(ao<=.95?1.0:0.0);
  if(face&&matIdR>=.1)strength=0.0;
  float t=npcSmooth((rampCoordinate-position)/width);
  return base+npcSat(t*(1.0-t))*(target-base)*strength;
}
float npcAmbientWeight(float rampCoordinate,float isSkin,float amount){
  float t=npcSat((rampCoordinate-uMat[14].x)/(uMat[14].y-uMat[14].x));
  t=mix(t,rampCoordinate,isSkin);
  float strength=npcSat(uAmbientStrength);
  t=mix(strength*uMat[14].z,strength*1.1,t);
  t=mix(t,strength*uMat[14].w,isSkin);
  return mix(t,strength,amount);
}
vec2 npcMatcapUV(vec3 N){
  vec3 n=uViewRotation*N;
  vec3 p=normalize(uViewRotation*(vWorldPosition-cameraPosition));
  // uViewRotation must produce UE-style view axes, positive Z forward.
  return .5+.5*vec2(n.x*p.z-n.z*p.x,p.y*n.z-n.y*p.z);
}

// Original view/sun controlled rim, without the optional scene override
// (CB4[16..19]). Runtime override is zero in this studio variant.
vec3 npcRim(vec3 base,vec3 N,vec3 V,float amount,float ao,bool face){
  vec3 geometricN=vNormal;
  float d=npcSmooth(min(abs(dot(vWorldPosition,uCameraForward))*.01,1.0));
  float side=npcSmooth((abs(dot(normalize(N),normalize(uCameraRight)))-.2)/(.8-.1*d));
  float orientation=1.0-(.9+.1*d)*side;
  float radial=1.0;
  if(face){float radius=.25-.25*uMat[51].z;radial=npcSmooth((length(vUv-vec2(.5,.35))-radius)/.45);}
  float noV=npcSat(dot(geometricN,V));
  float edge=1.0-npcSat((noV-.05)/max(.4-.4*abs(dot(V,uBasisZ)),1e-6));
  float power=face?uMat[38].x:uMat[34].x;
  float soft=face?uMat[38].y:uMat[34].y;
  float intensity=face?uMat[51].w:uMat[54].y;
  float rim=npcSat((pow(max(orientation*radial*(1.0-noV)*edge,0.0),power)-.5)/soft);
  rim*=min(amount+.3,1.0)*(face?min(ao,1.0):min(ao*2.0,1.0))*intensity*vColor.r;
  return rim*mix(uLightColor*.5,uLightColor,amount)*clamp(base+.1,0.0,1.0)*uRimEnabled;
}

vec3 npcBodySurface(){
  vec4 packed=texture2D(uMask,vUv);
  vec3 id=texture2D(uId,vUv).rgb;
  vec3 N=npcNormal(packed),L=normalize(uLightDir),V=normalize(cameraPosition-vWorldPosition);
  float noL=dot(N,L),halfL=noL*.5+.5;
  float region=npcRegion(id),isSkin=(region>=4.5?1.0:0.0)*uMat[13].x;
  float ao=npcSat(packed.b),adjustedAO=ao;
  if(region>=2.0&&region<=4.0)adjustedAO=max(ao,.5);
  float mixedAO=(adjustedAO+halfL)*.5;
  if(adjustedAO>.95)mixedAO=1.0;
  if(adjustedAO<.05)mixedAO=0.0;
  float f=npcSat(noL)*(1.0-id.g)+id.g;
  float fmin=min(f,mixedAO);
  f=fmin+halfL*(mixedAO-fmin);
  f=npcSat((f-uMat[8].x)/(uMat[8].y*.1));
  f=min(f,min(ao*2.0,1.0));
  if(f>.95)f=1.0;
  float amount=npcMainAmount(f);
  vec3 H=normalize(V+L);
  // UE XY is horizontal; after (x,z,-y), preview XZ is horizontal.
  vec3 reverseH=normalize(V+L*vec3(-1.0,1.0,-1.0));
  float noH=mix(npcSat(dot(N,reverseH)),npcSat(dot(N,H)),amount);
  float spec=npcSpecKernel(noH,packed.a,npcSpecParameters(region,false));
  spec*=.3+1.7*amount;
  float allowUnlit=1.0-((id.r>=.59&&id.r<=.79)?1.0:0.0);
  float specAmount=amount*spec+allowUnlit*(spec-amount*spec);
  vec4 matcap=npcSRGB(texture2D(uMatcap,npcMatcapUV(N)).rgb).rgbr;
  // Alpha is not SRGB decoded by the GPU.
  matcap.a=texture2D(uMatcap,npcMatcapUV(N)).a;
  float rough=uMat[28].x;
  float cap=mix(matcap.r,matcap.g,npcSat(rough*3.0));
  cap=mix(cap,matcap.b,npcSat(rough*3.0-1.0));
  cap=mix(cap,matcap.a,npcSat(rough*3.0-2.0));
  cap=mix(1.0,cap,uMat[31].x);
  float capIntensity=npcSat(cap*uMat[31].y)*(packed.a>=.1?1.0:0.0);
  float capValue=mix(uMat[31].w,uMat[31].z,capIntensity);
  float capAO=npcSmooth((packed.a-1.0)/(-.08*capValue*capValue*capValue-.02));
  float capShade=mix(capValue*.5,capValue*1.5-.5*capValue*capAO,amount);
  float rampCoordinate=1.0-npcSat((uMat[8].x-noL)/(uMat[8].x*uMat[8].z+.0001));
  vec3 base=npcDesaturate(npcRampBase(npcBaseSample(),amount,ao,isSkin,rampCoordinate,false,id.r));
  float metal=(id.r>=.79?1.0:0.0),f0=(metal>0.0?.04:1.0);
  vec3 diffuseBase=base*f0;
  vec3 metalBase=base*capShade*metal+diffuseBase;
  vec3 direct=diffuseBase*amount+metalBase*specAmount;
  float ambWeight=npcAmbientWeight(rampCoordinate,isSkin,amount);
  vec3 rampTint=vec3(1.0)+.2*isSkin*(uMat[11].rgb-1.0);
  vec3 tint=mix(uAmbientColor*rampTint,vec3(1.0),npcSat(uAmbientDesaturation));
  vec3 ambientBase=metalBase*ambWeight*uAmbientScale;
  vec3 metalAmbient=ambientBase*tint*cap*(1.0+amount*(dot(uLightColor,vec3(.375,.5,.125))-1.0));
  vec3 color=direct*(uLightColor+min(uAmbientDarkAdd,0.0))+ambientBase*tint+metal*metalAmbient;
  color+=min(uAmbientDarkAdd,0.0)*(metal*metalAmbient+metalBase*(1.0+specAmount));
  color+=npcRim(base,N,V,amount,ao,false);
  return color*uMat[41].rgb;
}

// SDF-style face light and its pre-threshold gradient, reused by ramp/ambient.
vec2 npcFaceShadow(){
  vec3 F=normalize(uBasisY),R=normalize(uBasisX),plane=cross(F,R);
  vec3 L=normalize(uLightDir);
  // CustomMainLightDir overrides light only when its stored alpha is enabled.
  vec3 overrideL=uBasisX*uMat[18].x+uBasisY*uMat[18].y+uBasisZ*uMat[18].z;
  L=mix(L,overrideL,uMat[46].x);
  L=normalize(L-plane*dot(L,plane));
  float halfL=dot(F,L)*.5+.5;
  float side=sign(dot(L,R));
  float face=texture2D(uFace,vec2(vUv.x*side,vUv.y)).r;
  float gap=npcSat(face-(1.0-halfL));
  float directionalGap=gap*npcSat(halfL*10.0);
  float x=(.5+directionalGap)*.5;
  float f=npcSmooth((x-uMat[8].x)/(uMat[8].y*.5));
  return vec2(f,directionalGap);
}
vec3 npcFaceSurface(){
  vec4 packed=texture2D(uMask,vUv);
  vec3 id=texture2D(uId,vUv).rgb;
  vec3 N=vNormal,L=normalize(uLightDir),V=normalize(cameraPosition-vWorldPosition);
  vec2 face=npcFaceShadow();
  float ao=npcSat(packed.b);
  float amount=npcMainAmount(face.x*(ao>=.05?1.0:0.0));
  float region=npcRegion(id),isSkin=(region>=4.5?1.0:0.0);
  float noH=npcSat(dot(N,normalize(V+L)));
  float spec=npcSpecKernel(noH,packed.a,npcSpecParameters(region,true));
  spec*=amount*(.3+1.7*amount);
  float rampCoordinate=1.0-face.y/(uMat[8].z+.0001);
  vec3 base=npcDesaturate(npcRampBase(npcBaseSample(),amount,ao,isSkin,rampCoordinate,true,id.r));
  vec3 direct=base*(amount+spec);
  float ambWeight=npcAmbientWeight(rampCoordinate,isSkin,amount);
  vec3 tint=mix(uAmbientColor*(vec3(1.0)+.2*(uMat[11].rgb-1.0)),vec3(1.0),npcSat(uAmbientDesaturation));
  vec3 color=direct*(uLightColor+min(uAmbientDarkAdd,0.0))+base*ambWeight*uAmbientScale*tint;
  color+=min(uAmbientDarkAdd,0.0)*base*(1.0+spec);
  color+=npcRim(base,N,V,amount,ao,true);
  return color*uMat[37].rgb;
}
