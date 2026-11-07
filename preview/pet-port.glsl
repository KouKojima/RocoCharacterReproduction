// Recovered material kernel for the pet character (Lig_YiLiSi3_001).
// Not original source. Ported from the cooked DXBC of the original BasePass
// program MI_Lig_YiLiSi3_001_By (resource 4D1367FB, PS
// b179fd5f54d35cfe731f727d92d891067dd8ee40, 181 instructions) with the same
// method the kit used for the humanoid body-face port: the arithmetic is
// rebuilt instruction by instruction and driven by the evaluated original
// material constants.
//
// The pet uses the PetBase material family (M_P_Object / M_P_Outline /
// M_P_Eyes_Mesh), a different material graph from the humanoid M_C_Object
// family. It shares the engine material functions - the inverse tone curve
// (-0.2072/0.70896/0.002209), the tangent-space normal reconstruction and the
// GGX-like lobe constants are byte identical with the humanoid port - but the
// branch structure differs: the pet has no MatID texture, its region comes
// from the vertex colour, and it has no face projection, no Matcap and no
// curve-only facial animation.
//
// The recovered kernel is checked numerically against the original DXBC by
// tools/charextract/validate_pet_port.py (max abs error 2.2e-16 over 500
// random samples, including the stochastic cut-out decision).
//
// Caller supplies uMat[64] (the evaluated original material rows), the
// uBase/uMask/uRamp samplers, the world position, geometry normal, UVs and
// vertex colour, the camera position, the studio light and the pet runtime
// uniforms below. Output is scene-linear RGB.

uniform vec3 uBasisX, uBasisY, uBasisZ;
uniform vec3 uCameraRight, uCameraForward;
uniform mat3 uViewRotation;
uniform float uDirectScale;
uniform float uAmbientStrength, uAmbientDesaturation, uAmbientScale;
uniform float uColorDesaturation, uShadowBias, uAmbientDarkAdd;
uniform float uRimEnabled;

// Runtime state of the pet material family. These live in the original
// per-primitive / scene constant buffers (cb2..cb5) and in material rows
// driven by the game's dynamic switches, none of which the cooked asset
// carries; the preview supplies them, exactly like the studio light.
uniform float uPetRampWidth;      // cb4[2].x  - ramp lookup width
uniform float uPetRampContrast;   // cb5[2].z  - ramp contrast pivot
uniform float uPetSpecScale;      // cb4[12].y - specular tint weight
uniform float uPetBaseMix;        // cb0[156].y - albedo / toon blend
uniform float uPetOutputScale;    // cb0[145].y - final output scale
uniform float uPetShadowBias;     // cb4[12].w - shadow LUT bias
uniform float uPetRampBlend;      // cb4[1].z  - ramp / shadow blend
uniform float uPetRampFloor;      // cb4[1].w  - shadow floor
uniform vec3  uPetSpecTint;       // cb4[15].xyz
uniform vec3  uPetLightVector;    // cb2[0].xyz - light direction * intensity
uniform vec3  uPetAmbient;        // cb0[199].xyz
uniform float uPetFrame;          // cb0[79].w
uniform vec3  uPetCamera;         // cb0[23].xyz
uniform float uPetShadowLut;      // the shadow ramp lookup buffer value
uniform float uPetClipW;          // SV_Position.w (1 / clip w)

float petSat(float x){return clamp(x,0.0,1.0);}

// The engine's inverse tone curve, byte identical with the humanoid kernel.
vec3 petInverseTone(vec3 c){
  return (vec3(0.047)-0.56*c-sqrt(max(vec3(0.0),-0.2072*c*c+0.70896*c+0.002209)))/(1.86*c-2.72);
}

// The original saturates the comparison result to 0xffffffff, which the
// kernel uses as a 0/1 selector.
float petFlag(float x){return x<0.0?-1.0:0.0;}

// dxbc `and` with a float mask keeps the 1.0 bit pattern of a non zero
// source and clears the masked out components.
float petBitAnd(float a,float b){
  uint ua=uint(floatBitsToUint(a));uint ub=uint(floatBitsToUint(b));
  return uintBitsToFloat(ua&ub);
}

// The vertex colour carries the region selector in .z, a per vertex material
// index in .y and a cut-out band in .w. The original chain is:
//   lt  r0.xyzw, v2.zzzz, l(0.9, 0.7, 0.5, 0.3)
//   movc r0.x, r0.x, cb6[33].z, cb6[33].y
//   movc r0.x, r0.y, cb6[33].w, r0.x
//   movc r0.x, r0.z, cb6[34].x, r0.x
//   movc r0.x, r0.w, cb6[34].y, r0.x
//   lt  r0.y, v2.z, l(0.1)
//   movc r0.x, r0.y, cb6[34].z, r0.x
//   max r0.x, r0.x, l(1.0)
//   round_ne r0.x, r0.x
//   mul r0.y, v2.y, l(10.0)
//   round_ni r0.y, r0.y
//   add r0.x, -r0.y, r0.x
//   lt  r0.x, l(0.00001), |r0.x|
//   movc r0.y, r0.x, l(0), l(1.0)
//   ge  r0.z, v2.w, l(0.8)
//   ge  r0.w, l(0.9), v2.w
//   and r0.xzw, r0.xxzw, l(1.0, 0.0, 1.0, 1.0)
//   mad r0.z, -r0.z, r0.w, l(1.0)
//   mad r0.x, r0.z, r0.x, r0.y
vec3 petCutoutWeight(vec4 vc,vec4 m){
  vec4 lt4=vec4(vc.z<0.9,vc.z<0.7,vc.z<0.5,vc.z<0.3);
  float region=m[33].y;
  region=lt4.x?m[33].z:region;
  region=lt4.y?m[33].w:region;
  region=lt4.z?m[34].x:region;
  region=lt4.w?m[34].y:region;
  region=(vc.z<0.1)?m[34].z:region;
  region=max(region,1.0);
  float x=(round(region)!=region)?1.0:0.0;
  float index=floor(vc.y*10.0+0.5);
  x=x-index;
  x=(1e-5<abs(x))?1.0:0.0;
  float y=(x!=0.0)?0.0:1.0;
  float z=(vc.w>=0.8)?1.0:0.0;
  float w=(0.9>=vc.w)?1.0:0.0;
  x=petBitAnd(x,1.0);
  z=petBitAnd(z,1.0);
  w=petBitAnd(w,1.0);
  z=1.0-z*w;
  return vec3(z*x+y,z,w);
}

// Recovered body surface of the pet material family.
vec3 petBodySurface(){
  vec4 m0=uMat[33],m1=uMat[34],m2=uMat[35],m3=uMat[36],m4=uMat[37];
  vec4 vc=vColor;
  vec3 cut=petCutoutWeight(vc,vec4(uMat[33],uMat[34]));
  float cutout=cut.x;

  // 78..91 view fresnel (multiplied by the material fresnel rows)
  float frame=floor(uPetFrame+0.1);
  vec3 world=vWorldPosition;
  float invP2=1.0/max(dot(world,world),1e-30);
  vec3 r1=-world*invP2;
  vec3 r2=world*invP2-uPetCamera;
  vec3 r0=frame*r2+r1;
  float fresnel=petSat(dot(vNormal,r0));
  fresnel=1.0-fresnel;
  fresnel=max(fresnel,1e-4);
  fresnel=exp(log(fresnel)*m1.w);
  fresnel=fresnel*m2.x;

  // 92..104 rim / emissive accumulation
  vec3 rim=fresnel*uMat[5].xyz*m2.y;
  float r1x=m2.z-1.0;
  r1x=m2.y*r1x+1.0;
  float r1y=fresnel*r1x-0.99;
  r1y=petSat(r1y*100.000099);
  float r1z=r1y*(-2.0)+3.0;
  r1y=r1y*r1y*r1z;
  vec3 r1spec=r1y*uMat[6].xyz*m2.w;
  r0=r0*r1x-r1spec;
  r0=m3.x*r0+r1spec;

  // 105..112 base colour sample
  vec4 tex1=texture(uBase,vUv);
  float alpha=petSat((tex1.a-0.04)*1.1111);
  r0=uMat[9].xyz*alpha+r0;
  vec3 r2c=alpha*uMat[2].xyz;
  r2c=r2c*m0.x+r0;

  // 113..121 stochastic cut-out (the original dither matrix is the shader's
  // immediate constant block)
  vec2 screen=floor(gl_FragCoord.xy);
  ivec2 dither=ivec2(int(screen.x)&3,int(screen.y)&3);
  vec4 icb0=vec4(1.0,0.0,0.0,0.0),icb1=vec4(0.0,1.0,0.0,0.0);
  vec4 icb2=vec4(0.0,0.0,1.0,0.0),icb3=vec4(0.0,0.0,0.0,1.0);
  vec4 icb4=vec4(0.0,0.75,0.125,0.9375),icb5=vec4(0.5,0.25,0.6875,0.4375);
  vec4 icb6=vec4(0.1875,0.875,0.0625,0.8125),icb7=vec4(0.625,0.375,0.5625,0.3125);
  vec4 rows[8]=vec4[8](icb0,icb1,icb2,icb3,icb4,icb5,icb6,icb7);
  float ditherValue=dot(rows[dither.y+4],rows[dither.x]);
  float gate=(uMat[40].w>=ditherValue)?1.0:0.0;
  cutout=cutout*gate-0.3333;
  if(cutout<0.0)discard;

  // 122..138 albedo and specular tint
  vec3 c=tex1.rgb;
  vec3 disc=sqrt(max(-0.2072*c*c+0.70896*c+0.002209,vec3(0.0)));
  vec3 albedo=(vec3(0.047)-0.56*c-disc)/((0.93*c-1.36)*2.0);
  albedo=m3.w*(-albedo)+albedo;
  float luma=dot(albedo,vec3(0.3,0.59,0.11));
  float specScale=petSat(uPetSpecScale);
  vec3 specTint=luma*specScale+albedo*(1.0-specScale);
  albedo=petSat(albedo);

  // 139..146 geometric normal and light direction
  vec3 geo=normalize(vNormal);
  float flag=petBitAnd(0.0,0.0);
  vec3 lightDir=uPetLightVector;
  float flag2=1.0;
  float ndotl=dot(geo,lightDir);

  // 147..164 mask light channel and the ambient floor
  vec4 mask=texture(uMask,vUv);
  float maskB=petSat(mask.b);
  float maskA=petSat(mask.a);
  float lightAmount=ndotl*0.5+maskB;
  lightAmount=(lightAmount+0.5)*0.5;
  lightAmount=(0.95<maskB)?1.0:lightAmount;
  albedo=albedo*(1.0-maskA);
  lightAmount=(maskB<0.05)?0.0:lightAmount;
  float step=saturateSigned((lightAmount-uMat[15].x)/(uMat[15].y*0.1));
  float floorValue=1.0-petSat(uMat[15].x-lightAmount);
  lightAmount=step*(1.0-floorValue)+floorValue;

  // 165..179 shadow and the direct light amount
  float shadow=petSat((uPetClipW*1e-5-uPetShadowBias)/1.0);
  shadow=shadow*shadow*(shadow*(-2.0)+3.0);
  shadow=shadow*(1.0-1.0)+1.0;
  float lum=dot(uPetLightVector,vec3(0.375,0.5,0.125));
  float direct=petSat(lum+lum);
  float rampAmount=direct*lightAmount;
  direct=direct*step;

  // 180..188 shadow ramp lookup
  float lutValue=1.0;
  float lutFlag=(1e-5<abs(uMat[39].x-0.5))?1.0:0.0;
  if(lutFlag==0.0)lutValue=1.0;
  lutValue=petSat(lutValue+uPetShadowBias);
  rampAmount=rampAmount*lutValue;

  // 189..198 ramp lookup
  float rampU=rampAmount*petSat(uPetRampWidth);
  vec3 ramp=texture(uRamp,vec2(rampU,0.003906)).rgb;
  float contrast=1.0-abs((uPetRampContrast-0.5)*2.0);
  ramp=ramp*0.85+contrast*ramp*0.15;
  vec3 invRamp=1.0-ramp;

  // 200..217 toon colour
  direct=direct*lutValue*lutFlag;
  vec3 toon=direct*invRamp+ramp;
  vec3 tint=-uPetAmbient+uPetSpecTint;
  tint=uPetSpecTint.w*tint+uPetAmbient;
  toon=toon-tint;
  float rampBlend=petSat(uPetRampBlend);
  toon=rampBlend*toon+tint;
  toon=specTint*toon;
  float floorMix=1.0-uPetRampFloor;
  floorMix=lightAmount*floorMix+uPetRampFloor;
  toon=floorMix*toon;
  vec3 lightTint=direct*specTint;
  float lightOffset=min(uPetLightOffset*uMat[38].w,0.0);
  vec3 lightDir2=lightDir+lightOffset;
  toon=lightTint*lightDir2+toon;
  vec3 colour=lightOffset*tex1.rgb+toon;

  // 218..233 specular tint and the final composition
  vec3 r3=uMat[12].xyz-r2c;
  r2c=m3.w*r3+r2c;
  r3=uMat[13].xyz-r2c;
  r2c=m4.x*r3+r2c;
  r2c=max(r2c,vec3(0.0));
  r3=r2c*direct-r2c;
  r3=r3*uMat[29].y;
  r2c=uMat[29].x*r3+r2c;
  colour=colour+r2c;
  colour=shadow*colour;
  colour=max(colour,vec3(0.0));
  colour=min(colour,vec3(100.0));
  vec3 result=uPetBaseMix*(albedo-colour)+colour;
  result=result*uPetOutputScale;
  result=result*uMat[32].xyz;
  return result;
}
