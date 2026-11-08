// Original NPC outline semantic port. Source VS: ba0f79aa7e2032de...
// Source PS: 758ab8acf6923046... (F61D1B9E resource map).
// Geometry positions use meters; source WPO distance constants use centimeters.
// Caller provides world-space tangent/normal after native skinning/model transform.
// Packed smooth-normal variant uses UV1 as signed tangent-space XY, WITHOUT remap.

float nrcOutlineSmooth01(float t) {
    t = clamp(t, 0.0, 1.0);
    return t * t * (3.0 - 2.0 * t);
}

vec3 nrcOutlineSmoothNormal(vec3 worldNormal, vec4 worldTangent,
                            vec2 signedUV1, bool useSmoothNormal) {
    if (!useSmoothNormal) return worldNormal;
    vec3 bitangent = cross(worldNormal, worldTangent.xyz) * worldTangent.w;
    float z = sqrt(1.0 - min(dot(signedUV1, signedUV1), 1.0));
    return normalize(worldTangent.xyz * signedUV1.x
                   + bitangent * signedUV1.y + worldNormal * z);
}

// Perspective-camera port, including source pixel-width min/max clamps.
// widthParams = (OutlineWidthPC, DistanceUniform, MaxWidthScale,
//                OutlineOffset in native centimeters).
// uMat rows in F61D1B9E: widthParams=(uMat[9].w,uMat[10].y,
//                                  uMat[10].z,uMat[10].w).
// customClip = uMat[10].x; offsetDirM = uMat[7].xyz * 0.01.
// aspectCorrection = abs(View[139].z * View[139].y) in source;
// default inference with ViewSizeAndInvSize is viewport.y / viewport.x.
// Non-smooth 5B0C variant hardcodes ray offset 10cm: pass widthParams.w=10.
vec3 nrcOutlineWorldPosition(
    vec3 worldPositionM, vec3 normalForOutline, vec4 vertexColor,
    vec2 viewport, vec3 cameraPositionM,
    mat4 viewMatrix, mat4 projectionMatrix, mat4 inverseViewProjection,
    vec4 widthParams, float customClip, float aspectCorrection,
    vec3 offsetDirM
) {
    vec4 clip = projectionMatrix * viewMatrix * vec4(worldPositionM, 1.0);
    vec2 direction = (projectionMatrix * viewMatrix
                     * vec4(normalForOutline, 0.0)).xy + vec2(0.000001);
    direction = normalize(direction);
    float depthCM = abs(clip.w) * 100.0;
    float distantScale = 1.0 - 0.55
        * nrcOutlineSmooth01((depthCM - 1000.0) * 0.005);
    float closeScale = 0.8 + 1.4
        * nrcOutlineSmooth01((depthCM - 50.0) * 0.02);
    float green = clamp(vertexColor.g, 0.0, 1.0);
    float enabled = step(0.1, green);
    float projectionScale = mix(1.0, abs(projectionMatrix[1][1]),
                               widthParams.y);
    float radiusCM = green * widthParams.x * closeScale * projectionScale;
    vec2 pixelToClipCM = max(2.0 * clip.w * 100.0
                            / max(viewport, vec2(1.0)), vec2(0.000001));
    vec2 pixelOffset = direction * radiusCM;
    pixelOffset.x *= aspectCorrection;
    pixelOffset = pixelOffset / pixelToClipCM * enabled;
    float baseWidthPX = max(viewport.y * 0.000926, 0.6);
    float minWidthPX = baseWidthPX * distantScale;
    float maxWidthPX = baseWidthPX * widthParams.z;
    pixelOffset *= max(minWidthPX
                       / max(length(pixelOffset), 0.000001), 1.0);
    vec2 enabledAxes = step(vec2(0.000001), abs(pixelOffset));
    vec2 signedMinimum = max(abs(pixelOffset), enabledAxes * minWidthPX)
                         * sign(pixelOffset);
    if (length(signedMinimum) >= maxWidthPX) {
        signedMinimum = normalize(signedMinimum + vec2(0.000001))
                        * maxWidthPX;
    }
    // The source uses reversed-Z [0,1]. Three.js uses regular-Z [-1,1];
    // source clip.z -= CustomClip*clip.w becomes +2*CustomClip*clip.w here.
    clip.xy += signedMinimum * pixelToClipCM * 0.01;
    clip.z += 2.0 * customClip * clip.w * enabled;
    // Source deliberately reads xyz of the inverse transform without divide.
    vec3 expandedWorld = (inverseViewProjection * clip).xyz;
    vec3 rayDirection = normalize(worldPositionM - cameraPositionM);
    return expandedWorld + rayDirection * vertexColor.a * widthParams.w * 0.01
           + offsetDirM;
}

vec3 nrcOutlineRGBtoHSV(vec3 c) {
    vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
    float d = q.x - min(q.w, q.y);
    // Shader has literal zero denominator guards; use epsilon to define gray.
    return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + 1e-10)),
                d / (q.x + 1e-10), q.x);
}

// Explicit source lookup UV; read T_Outline_Hue.R with this coordinate.
vec2 nrcOutlineHueUV(vec3 baseTextureMip4) {
    float hue = nrcOutlineRGBtoHSV(baseTextureMip4).x;
    return vec2(abs(hue) * 0.996 + 0.005, 0.0);
}

vec3 nrcOutlineHSVtoRGB(float hue, float saturation, float value) {
    // Source uses 0.667/0.333 rather than exact thirds.
    vec3 ramps = clamp(abs(fract(hue + vec3(0.0, 0.667, 0.333))
                           * 6.0 - 3.0) - 1.0, 0.0, 1.0);
    return (ramps * saturation + (1.0 - saturation)) * value;
}

// baseTextureMip4 must come from textureLod(BaseTex, uv, 4.0) after the same
// source sRGB interpretation. remappedHue = texture(T_Outline_Hue, hueUV).r.
// skinColor=uMat[2].rgb, customColorAndSwitch=uMat[4].rgb+uMat[8].z,
// intensity=uMat[8].w, selection=uMat[5].rgb+uMat[9].x.
vec3 nrcOutlineBaseColor(float matIdR, vec3 baseTextureMip4,
                         float remappedHue, bool highVariant,
                         vec3 skinColor, vec4 customColorAndSwitch,
                         float intensity, vec4 selectionColor) {
    float region = floor(min((1.0 - matIdR) * 5.0 + 1.0, 5.0));
    vec3 hsv = nrcOutlineRGBtoHSV(baseTextureMip4);
    vec3 otherColor = highVariant
        ? nrcOutlineHSVtoRGB(remappedHue, hsv.y * 1.2, hsv.z * 0.03 + 0.05)
        : vec3(0.014444, 0.005605, 0.035601);
    vec3 color = region <= 4.0 ? otherColor : skinColor;
    color = mix(color, customColorAndSwitch.rgb, customColorAndSwitch.a);
    color *= intensity;
    return mix(color, selectionColor.rgb, selectionColor.a);
}
