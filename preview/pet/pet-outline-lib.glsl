// Generated from the cooked DXBC of outline.
// Resource MI_Lig_YiLiSi3_001_By_Ol-2AECB4DE, program shader-f83ebd021113dc4b50c3e9cb16916e88c342d7cb.
// Not original source: a mechanical transpilation of the original program,
// checked against the original program by tools/charextract/validate_pet_port.py.
precision highp float;
precision highp int;
#define texture2D texture
uniform vec4 uMat[64];
uniform sampler2D uBase;
uniform sampler2D uMask;
uniform sampler2D uRamp;
uniform sampler2D uEyeAtlas;
uniform sampler2D uOutlineMask;
uniform vec4 uShadowLut;
vec4 pNormal;
vec4 pColor;
vec4 pUv;
vec4 pWorld;
vec4 pScreen;
vec4 pOutlineWidth;
// the interpreter starts with r0 = (1,1,1,0) and every other register at zero;
// the same initialisation keeps the GLSL registers comparable instruction by
// instruction (a shader global would otherwise be undefined).
vec4 r0=vec4(1.0,1.0,1.0,0.0),r1=vec4(0.0),r2=vec4(0.0),r3=vec4(0.0),r4=vec4(0.0),r5=vec4(0.0),r6=vec4(0.0),r7=vec4(0.0),r8=vec4(0.0),r9=vec4(0.0),r10=vec4(0.0),r11=vec4(0.0),r12=vec4(0.0),r13=vec4(0.0),r14=vec4(0.0),r15=vec4(0.0);
const vec4 icbRows[8]=vec4[8](vec4(1.0,0.0,0.0,0.0),vec4(0.0,1.0,0.0,0.0),vec4(0.0,0.0,1.0,0.0),
  vec4(0.0,0.0,0.0,1.0),vec4(0.0,0.75,0.125,0.9375),vec4(0.5,0.25,0.6875,0.4375),
  vec4(0.1875,0.875,0.0625,0.8125),vec4(0.625,0.375,0.5625,0.3125));
uniform vec4 uCb0_138;
uniform vec4 uCb0_145;
uniform vec4 uCb0_147;
uniform vec4 uCb0_153;
uniform vec4 uCb0_156;
uniform vec4 uCb0_199;
uniform vec4 uCb0_294;
uniform vec4 uCb1_79;
uniform vec4 uCb2_15;

vec4 petOut;
float petAux;
void petMain(){
r0.x = (vec4(dot((-pWorld.xyzx).xyz, (-pWorld.xyzx).xyz))).x;
r0.x = ((1.0 / sqrt(max(r0.xxxx, vec4(1e-30))))).x;
r0.xyz = ((r0.xxxx * (-pWorld.xyzx))).xyz;
r1 = (vec4(0.0) - vec4(lessThan(pColor.zzzz, vec4(0.9, 0.7, 0.5, 0.3))));
r0.w = ((uMat[18].xxxx + (uMat[18].yyyy - uMat[18].xxxx) * vec4(notEqual(r1.xxxx, vec4(0.0))))).w;
r0.w = ((r0.wwww + (uMat[18].zzzz - r0.wwww) * vec4(notEqual(r1.yyyy, vec4(0.0))))).w;
r0.w = ((r0.wwww + (uMat[18].wwww - r0.wwww) * vec4(notEqual(r1.zzzz, vec4(0.0))))).w;
r0.w = ((r0.wwww + (uMat[19].xxxx - r0.wwww) * vec4(notEqual(r1.wwww, vec4(0.0))))).w;
r1.x = (vec4(0.0) - vec4(lessThan(pColor.zzzz, vec4(0.1)))).x;
r0.w = ((r0.wwww + (uMat[19].yyyy - r0.wwww) * vec4(notEqual(r1.xxxx, vec4(0.0))))).w;
r0.w = (max(r0.wwww, vec4(1.0))).w;
r0.w = (vec4(1.0) - vec4(equal(round(r0.wwww), r0.wwww))).w;
r1.x = ((pColor.yyyy * vec4(10.0))).x;
r1.x = (floor(r1.xxxx + 0.5)).x;
r0.w = ((r0.wwww + (-r1.xxxx))).w;
r0.w = (vec4(0.0) - vec4(lessThan(vec4(1e-05), abs(r0.wwww)))).w;
r1.x = ((vec4(1.0) + (vec4(0.0) - vec4(1.0)) * vec4(notEqual(r0.wwww, vec4(0.0))))).x;
r1.y = (vec4(0.0) - vec4(greaterThanEqual(pColor.wwww, vec4(0.8)))).y;
r1.z = (vec4(0.0) - vec4(greaterThanEqual(vec4(0.9), pColor.wwww))).z;
r1.yz = (vec4(uintBitsToFloat(((uvec4(floatBitsToUint((r1.yyzy).x),floatBitsToUint((r1.yyzy).y),floatBitsToUint((r1.yyzy).z),floatBitsToUint((r1.yyzy).w)) & uvec4(uint(0), uint(1065353216), uint(1065353216), uint(0)))).x),uintBitsToFloat(((uvec4(floatBitsToUint((r1.yyzy).x),floatBitsToUint((r1.yyzy).y),floatBitsToUint((r1.yyzy).z),floatBitsToUint((r1.yyzy).w)) & uvec4(uint(0), uint(1065353216), uint(1065353216), uint(0)))).y),uintBitsToFloat(((uvec4(floatBitsToUint((r1.yyzy).x),floatBitsToUint((r1.yyzy).y),floatBitsToUint((r1.yyzy).z),floatBitsToUint((r1.yyzy).w)) & uvec4(uint(0), uint(1065353216), uint(1065353216), uint(0)))).z),uintBitsToFloat(((uvec4(floatBitsToUint((r1.yyzy).x),floatBitsToUint((r1.yyzy).y),floatBitsToUint((r1.yyzy).z),floatBitsToUint((r1.yyzy).w)) & uvec4(uint(0), uint(1065353216), uint(1065353216), uint(0)))).w))).yz;
r1.y = (((-r1.yyyy) * r1.zzzz + vec4(1.0))).y;
r0.w = (vec4(uintBitsToFloat(((uvec4(floatBitsToUint((r0.wwww).x),floatBitsToUint((r0.wwww).y),floatBitsToUint((r0.wwww).z),floatBitsToUint((r0.wwww).w)) & uint(1065353216))).x),uintBitsToFloat(((uvec4(floatBitsToUint((r0.wwww).x),floatBitsToUint((r0.wwww).y),floatBitsToUint((r0.wwww).z),floatBitsToUint((r0.wwww).w)) & uint(1065353216))).y),uintBitsToFloat(((uvec4(floatBitsToUint((r0.wwww).x),floatBitsToUint((r0.wwww).y),floatBitsToUint((r0.wwww).z),floatBitsToUint((r0.wwww).w)) & uint(1065353216))).z),uintBitsToFloat(((uvec4(floatBitsToUint((r0.wwww).x),floatBitsToUint((r0.wwww).y),floatBitsToUint((r0.wwww).z),floatBitsToUint((r0.wwww).w)) & uint(1065353216))).w))).w;
r0.w = ((r1.yyyy * r0.wwww + r1.xxxx)).w;
r1.xyz = ((uMat[2].xyzx * uMat[19].wwww)).xyz;
r2.xyz = (((-uMat[2].xyzx) * uMat[19].wwww + uMat[5].xyzx)).xyz;
r1.xyz = ((uMat[20].yyyy * r2.xyzx + r1.xyzx)).xyz;
r2.xyz = (((-r1.xyzx) + uMat[6].xyzx)).xyz;
r1.xyz = ((uMat[20].zzzz * r2.xyzx + r1.xyzx)).xyz;
r0.x = (vec4(dot((-pNormal.xyzx).xyz, r0.xyzx.xyz))).x;
r0.x = (max(r0.xxxx, vec4(0.0))).x;
r0.x = (((-r0.xxxx) + vec4(1.0))).x;
r0.x = (max(abs(r0.xxxx), vec4(0.0001))).x;
r0.x = ((r0.xxxx * r0.xxxx)).x;
r0.x = ((r0.xxxx * r0.xxxx)).x;
r0.x = ((r0.xxxx * r0.xxxx)).x;
r0.x = ((r0.xxxx * uMat[21].zzzz + uMat[21].yyyy)).x;
r0.yz = ((pUv.xxyx * uMat[8].xxyx + uMat[9].xxyx)).yz;
r0.yz = ((uMat[11].xxyx * uCb0_153.zzzz + r0.yyzy)).yz;
r0.y = ((texture(uOutlineMask, (r0.yzyy).xy)).yxzw).y;
r0.z = (vec4(0.0) - vec4(greaterThanEqual(vec4(0.0), r0.yyyy))).z;
r0.y = (log(max(r0.yyyy, vec4(1e-30)))).y;
r0.y = ((r0.yyyy * uMat[23].yyyy)).y;
r0.y = (exp(r0.yyyy)).y;
r0.y = ((r0.yyyy + (vec4(0.0) - r0.yyyy) * vec4(notEqual(r0.zzzz, vec4(0.0))))).y;
r0.z = (vec4(0.0) - vec4(greaterThanEqual(vec4(0.0), pOutlineWidth.xxxx))).z;
r1.w = (log(max(pOutlineWidth.xxxx, vec4(1e-30)))).w;
r1.w = ((r1.wwww * uMat[23].zzzz)).w;
r1.w = (exp(r1.wwww)).w;
r0.z = ((r1.wwww + (vec4(0.0) - r1.wwww) * vec4(notEqual(r0.zzzz, vec4(0.0))))).z;
r1.w = (((-r0.zzzz) * r0.zzzz + r0.zzzz)).w;
r0.y = (((-r0.zzzz) * r0.zzzz + r0.yyyy)).y;
r0.z = ((vec4(1.0, 1.0, 1.0, 1.0) / r1.wwww)).z;
r0.y = (clamp((r0.zzzz * r0.yyyy), 0.0, 1.0)).y;
r0.z = ((r0.yyyy * vec4(-2.0) + vec4(3.0))).z;
r0.y = ((r0.yyyy * r0.yyyy)).y;
r0.y = ((r0.yyyy * r0.zzzz)).y;
r0.x = ((r0.yyyy * r0.xxxx)).x;
r0.y = ((r0.xxxx * r0.wwww + (-r0.xxxx))).y;
r0.x = ((uMat[23].wwww * r0.yyyy + r0.xxxx)).x;
r0.y = (((-r0.xxxx) + vec4(1.0))).y;
r0.y = (max(r0.yyyy, uMat[29].xxxx)).y;
r0.y = (vec4(0.0) - vec4(lessThan(vec4(0.01), r0.yyyy))).y;
r0.z = (vec4(0.0) - vec4(greaterThanEqual(uMat[29].wwww, vec4(0.001)))).z;
r0.yz = (vec4(uintBitsToFloat(((uvec4(floatBitsToUint((r0.yyzy).x),floatBitsToUint((r0.yyzy).y),floatBitsToUint((r0.yyzy).z),floatBitsToUint((r0.yyzy).w)) & uvec4(uint(0), uint(1065353216), uint(1065353216), uint(0)))).x),uintBitsToFloat(((uvec4(floatBitsToUint((r0.yyzy).x),floatBitsToUint((r0.yyzy).y),floatBitsToUint((r0.yyzy).z),floatBitsToUint((r0.yyzy).w)) & uvec4(uint(0), uint(1065353216), uint(1065353216), uint(0)))).y),uintBitsToFloat(((uvec4(floatBitsToUint((r0.yyzy).x),floatBitsToUint((r0.yyzy).y),floatBitsToUint((r0.yyzy).z),floatBitsToUint((r0.yyzy).w)) & uvec4(uint(0), uint(1065353216), uint(1065353216), uint(0)))).z),uintBitsToFloat(((uvec4(floatBitsToUint((r0.yyzy).x),floatBitsToUint((r0.yyzy).y),floatBitsToUint((r0.yyzy).z),floatBitsToUint((r0.yyzy).w)) & uvec4(uint(0), uint(1065353216), uint(1065353216), uint(0)))).w))).yz;
r0.y = (max(r0.zzzz, r0.yyyy)).y;
r0.y = (vec4(0.0) - vec4(lessThan(vec4(0.5), r0.yyyy))).y;
if (any(greaterThan(abs(r0.yyyy), vec4(0.0)))) {
r0.x = (clamp(r0.xxxx, 0.0, 1.0)).x;
r0.yz = ((pScreen.xxyx + (-uCb0_138.xxyx))).yz;
r0.yz = (vec4(uintBitsToFloat((uvec4(ivec4(trunc(r0.yyzy)))).x),uintBitsToFloat((uvec4(ivec4(trunc(r0.yyzy)))).y),uintBitsToFloat((uvec4(ivec4(trunc(r0.yyzy)))).z),uintBitsToFloat((uvec4(ivec4(trunc(r0.yyzy)))).w))).yz;
r0.yz = (vec4(uintBitsToFloat(((uvec4(floatBitsToUint((r0.yyzy).x),floatBitsToUint((r0.yyzy).y),floatBitsToUint((r0.yyzy).z),floatBitsToUint((r0.yyzy).w)) & uvec4(uint(0), uint(3), uint(3), uint(0)))).x),uintBitsToFloat(((uvec4(floatBitsToUint((r0.yyzy).x),floatBitsToUint((r0.yyzy).y),floatBitsToUint((r0.yyzy).z),floatBitsToUint((r0.yyzy).w)) & uvec4(uint(0), uint(3), uint(3), uint(0)))).y),uintBitsToFloat(((uvec4(floatBitsToUint((r0.yyzy).x),floatBitsToUint((r0.yyzy).y),floatBitsToUint((r0.yyzy).z),floatBitsToUint((r0.yyzy).w)) & uvec4(uint(0), uint(3), uint(3), uint(0)))).z),uintBitsToFloat(((uvec4(floatBitsToUint((r0.yyzy).x),floatBitsToUint((r0.yyzy).y),floatBitsToUint((r0.yyzy).z),floatBitsToUint((r0.yyzy).w)) & uvec4(uint(0), uint(3), uint(3), uint(0)))).w))).yz;
r0.y = (vec4(dot(icbRows[(int(floatBitsToUint(r0.z)) + 4)], icbRows[(int(floatBitsToUint(r0.y)) + 0)]))).y;
r0.y = (vec4(0.0) - vec4(greaterThanEqual(uMat[30].wwww, r0.yyyy))).y;
r0.y = (vec4(uintBitsToFloat(((uvec4(floatBitsToUint((r0.yyyy).x),floatBitsToUint((r0.yyyy).y),floatBitsToUint((r0.yyyy).z),floatBitsToUint((r0.yyyy).w)) & uint(1065353216))).x),uintBitsToFloat(((uvec4(floatBitsToUint((r0.yyyy).x),floatBitsToUint((r0.yyyy).y),floatBitsToUint((r0.yyyy).z),floatBitsToUint((r0.yyyy).w)) & uint(1065353216))).y),uintBitsToFloat(((uvec4(floatBitsToUint((r0.yyyy).x),floatBitsToUint((r0.yyyy).y),floatBitsToUint((r0.yyyy).z),floatBitsToUint((r0.yyyy).w)) & uint(1065353216))).z),uintBitsToFloat(((uvec4(floatBitsToUint((r0.yyyy).x),floatBitsToUint((r0.yyyy).y),floatBitsToUint((r0.yyyy).z),floatBitsToUint((r0.yyyy).w)) & uint(1065353216))).w))).y;
r0.x = ((r0.xxxx * r0.yyyy + vec4(-0.3333))).x;
r0.x = (vec4(0.0) - vec4(lessThan(r0.xxxx, vec4(0.0)))).x;
if (any(greaterThan(abs(r0.xxxx), vec4(0.0)))) discard;
}
r0.xyz = (((-uCb0_199.xyzx) + uCb2_15.xyzx)).xyz;
r0.xyz = ((uCb2_15.wwww * r0.xyzx + uCb0_199.xyzx)).xyz;
r0.x = (vec4(dot(r0.xyzx.xyz, vec4(0.3, 0.59, 0.11, 0.0).xyz))).x;
r0.x = (clamp((r0.xxxx + r0.xxxx), 0.0, 1.0)).x;
r0.xyz = ((r1.xyzx * r0.xxxx + (-r1.xyzx))).xyz;
r0.xyz = ((uMat[20].wwww * r0.xyzx + r1.xyzx)).xyz;
r0.w = ((pScreen.wwww * vec4(1e-05) + (-uCb0_294.zzzz))).w;
r1.x = ((vec4(1.0, 1.0, 1.0, 1.0) / uCb0_294.wwww)).x;
r0.w = (clamp((r0.wwww * r1.xxxx), 0.0, 1.0)).w;
r1.x = ((r0.wwww * vec4(-2.0) + vec4(3.0))).x;
r0.w = ((r0.wwww * r0.wwww)).w;
r0.w = ((r0.wwww * r1.xxxx)).w;
r1.x = ((uCb0_294.yyyy + vec4(-1.0))).x;
r0.w = ((r0.wwww * r1.xxxx + vec4(1.0))).w;
r0.xyz = ((r0.wwww * r0.xyzx)).xyz;
r0.xyz = (max(r0.xyzx, vec4(0.0, 0.0, 0.0, 0.0))).xyz;
r0.xyz = (min(r0.xyzx, vec4(100.0, 100.0, 100.0, 0.0))).xyz;
r1.xyz = (((-r0.xyzx) + uCb0_147.xyzx)).xyz;
r0.xyz = ((uCb0_156.yyyy * r1.xyzx + r0.xyzx)).xyz;
petAux = ((pScreen.zzzz * uCb1_79.zzzz)).x;
r0.xyz = ((r0.xyzx * uCb0_145.yyyy)).xyz;
r1.xyz = ((r0.xyzx * uCb1_79.wwww)).xyz;
r0.w = (vec4(0.0) - vec4(lessThan(uCb1_79.wwww, vec4(1.0)))).w;
r1.xyz = (sqrt(max(r1.xyzx, vec4(0.0)))).xyz;
petOut.xyz = ((r0.xyzx + (r1.xyzx - r0.xyzx) * vec4(notEqual(r0.wwww, vec4(0.0))))).xyz;
petOut.w = (vec4(1.0)).w;
}
