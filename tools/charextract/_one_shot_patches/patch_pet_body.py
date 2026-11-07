import io

p = r'D:\洛克王国\洛克王国：世界(2002304)\_nrc_work\pet-port.glsl'
s = io.open(p, encoding='utf-8').read()

start = s.index('// Recovered body surface for the pet material family.')
end = s.index('// Recovered eye surface for the pet eye material.')

new = '''// Recovered body surface for the pet material family.
//
// The original pet program computes, in order:
//   1. a region id from the vertex colour (see petRegion)
//   2. the tangent-space normal from the mask texture (same engine function
//      as the humanoid port)
//   3. the base colour from uBase, with the alpha channel remapped
//      (add -0.04, mul_sat 1.1111)
//   4. a specular-mask adjusted NdotL that also feeds the ramp index
//   5. a GGX-like specular lobe with the pet's own parameter rows
//   6. the ramp lookup at (light amount * ramp width, 1/256)
//   7. the Fresnel rim and the final tone/output path
vec3 petBodySurface(){
  vec4 base=texture2D(uBase,vUv);
  vec4 packed=texture2D(uMask,vUv);
  vec3 N=petNormal(packed),L=normalize(uLightDir),V=normalize(cameraPosition-vWorldPosition);
  float noL=dot(N,L);

  // Base colour: the sampled colour goes through the same inverse tone curve
  // as the humanoid kernel, then the material's MainColor row.
  vec3 albedo=petInverseTone(petSRGB(base.rgb))*uMat[30].rgb;

  // Original alpha remap: add -0.04, mul_sat 1.1111.
  float alpha=petSat((base.a-0.04)*1.1111);

  float region=petRegion();
  float ao=petSat(packed.b);
  float specMask=packed.a;

  // Light amount. The original mixes the half-Lambert term with the mask
  // texture's own light channel:
  //   mad r2.w, r2.w, l(0.5), r3.x      ; r3.x = mask light channel
  //   add r2.w, r2.w, l(0.5)
  //   mul r2.w, r2.w, l(0.5)
  float light=petSat(noL*0.5+0.5);
  float maskLight=petSat(packed.r);
  float amount=petSat(light*0.5+maskLight)*0.5+0.5;
  amount=petSat(amount);

  // Specular: original GGX-like lobe using the pet's parameter rows.
  vec3 sp=petSpecParameters(region);
  vec3 H=normalize(L+V);
  float noH=max(dot(N,H),0.0);
  float noV=max(dot(N,V),1e-4);
  float a2=sp.x*sp.x;
  float d=a2/(3.14159*pow(noH*noH*(a2-1.0)+1.0,2.0));
  float vis=0.25/max(mix(2.0*noL*noV,noL+noV,0.5),1e-4);
  vec3 spec=d*vis*sp.y*specMask;

  // Ramp: the original samples the ramp texture with the accumulated light
  // amount as the horizontal coordinate and 1/256 as the vertical one:
  //   mov_sat r3.x, cb4[2].x
  //   mul    r5.x, r1.w, r3.x
  //   mov    r5.y, l(0.003906)
  //   sample r5.xyz, r5.xyxx, t3.xyzw
  // The ramp therefore encodes the light response as a 1D gradient.
  float rampIndex=petSat(amount)*uMat[14].x;
  vec3 ramp=petSRGB(texture2D(uRamp,vec2(rampIndex,0.003906)).rgb);

  // Fresnel rim, using the pet's Fresnel colour row.
  float fres=pow(1.0-noV,3.0);
  vec3 rim=uMat[5].xyz*fres*uRimEnabled;

  // The original alpha remap scales the diffuse contribution.
  vec3 direct=(albedo*amount*alpha+spec)*petMainAmount(amount)*uLightColor;
  vec3 ambient=albedo*petSat(uAmbientStrength)*uAmbientScale*uAmbientColor*ao;
  vec3 color=direct*mix(vec3(1.0),ramp,0.35)+ambient;
  color+=rim*amount;
  return color;
}

'''

s = s[:start] + new + s[end:]
io.open(p, 'w', encoding='utf-8').write(s)
print('pet body surface rewritten')
