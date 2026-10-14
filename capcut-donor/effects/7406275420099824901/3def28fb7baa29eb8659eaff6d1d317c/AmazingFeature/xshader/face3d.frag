#if defined(AE_FRAMEBUFFER_FETCH)
    #if defined(GL_EXT_shader_framebuffer_fetch)
        #extension GL_EXT_shader_framebuffer_fetch : require
    #elif defined(GL_ARM_shader_framebuffer_fetch)
        #extension GL_ARM_shader_framebuffer_fetch : require
    #endif
#endif
#define ae_insert_flip_uniform // FlipPatch will insert flip uniform here

precision highp float;

varying vec3 pos0;
varying vec2 uv0;
varying vec2 uv1;
varying vec3 normal0;

uniform vec3 u_WorldSpaceCameraPos;
uniform mat4 uModel;
uniform float uOpacity;

#ifdef AE_NORMALTEX_ENABLE
uniform sampler2D uNormalTexture;
#endif

// highlight
uniform float u_enableHighlight;
uniform float uHighlightOpacity;
uniform float uHighlightRoughness;
uniform float uHighlightMetallic;
uniform float uHighlightNormalInt;
uniform vec4 uHighlightColor;
uniform vec3 uHighlightDir;
uniform sampler2D uHighlightMask;

// sequin
uniform float u_enableSequin;
uniform float uSequinOpacity;
uniform float uSequinRoughness;
uniform float uSequinMetallic;
uniform float uSequinNormalInt;
uniform vec4 uSequinColor;
uniform vec3 uSequinPos;
uniform sampler2D uSequinMask;

// lip
uniform float u_enableLip;
uniform float uLipOpacity;
uniform sampler2D uUpperEnvTexture;
uniform sampler2D uUpperEnvMask;
uniform float uUpperEnvExposure;
uniform float uUpperEnvNormalInt;
uniform float uUpperEnvRotate;
uniform sampler2D uLowerEnvTexture;
uniform sampler2D uLowerEnvMask;
uniform float uLowerEnvExposure;
uniform float uLowerEnvNormalInt;
uniform float uLowerEnvRotate;

// mask
uniform float u_enableMask;
uniform float uMaskOpacity;
uniform vec3 uMaskColor;
uniform sampler2D uMaskTexture;

#ifdef AE_FACESEG_ENABLE
varying vec2 faceUV;
uniform float uFaceSegDetected;
uniform sampler2D uFaceSeg;
#endif

#ifdef AE_TEETHSEG_ENABLE
varying vec2 teethUV;
uniform float uTeethSegDetected;
uniform sampler2D uTeethSeg;
#endif

uniform sampler2D u_FBOTexture;
vec4 TextureFromFBO(vec2 uv)
{
    #if defined(AE_FRAMEBUFFER_FETCH)
        #if defined(GL_EXT_shader_framebuffer_fetch)
            vec4 result = gl_LastFragData[0].rgba;
        #elif defined(GL_ARM_shader_framebuffer_fetch)
            vec4 result = gl_LastFragColorARM;
        #else
            #error AE_FRAMEBUFFER_FETCH but no ext found!
        #endif
    #else
        vec4 result = texture2D(u_FBOTexture, uv);
    #endif
    return result;
}

const float fresnelPow = 5.0;
const float PI = 3.141592653;
const float F0Base = 0.04;

// blend----------------------------------------------------------------------------------------------
#if defined(AE_HIGHLIGHT_BLENDMODE_SCREEN) || defined(AE_SEQUIN_BLENDMODE_SCREEN) || defined(AE_MASK_BLENDMODE_SCREEN) || defined(AE_LIP_BLENDMODE_SCREEN)
vec3 BlendScreen(vec3 base, vec3 blend)
{
    return (1.0 - ((1.0 - base) * (1.0 - blend)));
}

vec3 BlendScreen(vec3 base, vec3 blend, float opacity)
{
    return (BlendScreen(base, blend) * opacity + base * (1.0 - opacity));
}
#endif

#if defined(AE_HIGHLIGHT_BLENDMODE_ADD) || defined(AE_SEQUIN_BLENDMODE_ADD) || defined(AE_MASK_BLENDMODE_ADD) || defined(AE_LIP_BLENDMODE_ADD)
vec3 BlendAdd(vec3 base, vec3 blend)
{
    return min(base + blend, vec3(1.0));
}

vec3 BlendAdd(vec3 base, vec3 blend, float opacity)
{
    return (BlendAdd(base, blend) * opacity + base * (1.0 - opacity));
}
#endif

#if defined(AE_HIGHLIGHT_BLENDMODE_MULTIPLY) || defined(AE_SEQUIN_BLENDMODE_MULTIPLY) || defined(AE_MASK_BLENDMODE_MULTIPLY) || defined(AE_LIP_BLENDMODE_MULTIPLY)
vec3 BlendMultiply(vec3 base, vec3 blend)
{
    return base * blend;
}

vec3 BlendMultiply(vec3 base, vec3 blend, float opacity)
{
    return (BlendMultiply(base, blend) * opacity + base * (1.0 - opacity));
}
#endif

#if defined(AE_HIGHLIGHT_BLENDMODE_OVERLAY) || defined(AE_SEQUIN_BLENDMODE_OVERLAY) || defined(AE_MASK_BLENDMODE_OVERLAY) || defined(AE_LIP_BLENDMODE_OVERLAY)
float BlendOverlay(float base, float blend)
{
    return base < 0.5 ? (2.0 * base * blend) : (1.0 - 2.0 * (1.0 - base) * (1.0 - blend));
}

vec3 BlendOverlay(vec3 base, vec3 blend)
{
    return vec3(BlendOverlay(base.r, blend.r), BlendOverlay(base.g, blend.g), BlendOverlay(base.b, blend.b));
}

vec3 BlendOverlay(vec3 base, vec3 blend, float opacity)
{
    return (BlendOverlay(base, blend) * opacity + base * (1.0 - opacity));
}
#endif

#if defined(AE_HIGHLIGHT_BLENDMODE_SOFTLIGHT) || defined(AE_SEQUIN_BLENDMODE_SOFTLIGHT) || defined(AE_MASK_BLENDMODE_SOFTLIGHT) || defined(AE_LIP_BLENDMODE_SOFTLIGHT)
float BlendSoftLight(float base, float blend)
{
    return (blend < 0.5) ? (2.0 * base * blend + base * base * (1.0 - 2.0 * blend)):(sqrt(base) * (2.0 * blend - 1.0) + 2.0 * base * (1.0 - blend));
}

vec3 BlendSoftLight(vec3 base, vec3 blend)
{
    return vec3(BlendSoftLight(base.r, blend.r), BlendSoftLight(base.g, blend.g), BlendSoftLight(base.b, blend.b));
}

vec3 BlendSoftLight(vec3 base, vec3 blend, float opacity)
{
    return (BlendSoftLight(base, blend) * opacity + base * (1.0 - opacity));
}
#endif

#if defined(AE_HIGHLIGHT_BLENDMODE_AVERAGE) || defined(AE_SEQUIN_BLENDMODE_AVERAGE) || defined(AE_MASK_BLENDMODE_AVERAGE) || defined(AE_LIP_BLENDMODE_AVERAGE)
vec3 BlendAverage(vec3 base, vec3 blend)
{
    return (base + blend) / 2.0;
}

vec3 BlendAverage(vec3 base, vec3 blend, float opacity)
{
    return (BlendAverage(base, blend) * opacity + base * (1.0 - opacity));
}
#endif

#if defined(AE_HIGHLIGHT_BLENDMODE_COLORBURN) || defined(AE_SEQUIN_BLENDMODE_COLORBURN) || defined(AE_MASK_BLENDMODE_COLORBURN) || defined(AE_LIP_BLENDMODE_COLORBURN)
float BlendColorBurn(float base, float blend)
{
    return (blend == 0.0) ? blend : max((1.0 - ((1.0 - base) / blend)),0.0);
}

vec3 BlendColorBurn(vec3 base, vec3 blend)
{
    return vec3(BlendColorBurn(base.r, blend.r), BlendColorBurn(base.g, blend.g), BlendColorBurn(base.b, blend.b));
}

vec3 BlendColorBurn(vec3 base, vec3 blend, float opacity)
{
    return (BlendColorBurn(base, blend) * opacity + base * (1.0 - opacity));
}
#endif

#if defined(AE_HIGHLIGHT_BLENDMODE_COLORDODGE) || defined(AE_SEQUIN_BLENDMODE_COLORDODGE) || defined(AE_MASK_BLENDMODE_COLORDODGE) || defined(AE_LIP_BLENDMODE_COLORDODGE)
float BlendColorDodge(float base, float blend)
{
    return (blend == 1.0) ? blend : min(base / (1.0 - blend), 1.0);
}

vec3 BlendColorDodge(vec3 base, vec3 blend)
{
    return vec3(BlendColorDodge(base.r, blend.r), BlendColorDodge(base.g, blend.g), BlendColorDodge(base.b, blend.b));
}

vec3 BlendColorDodge(vec3 base, vec3 blend, float opacity)
{
    return (BlendColorDodge(base, blend) * opacity + base * (1.0 - opacity));
}
#endif

#if defined(AE_HIGHLIGHT_BLENDMODE_DARKEN) || defined(AE_SEQUIN_BLENDMODE_DARKEN) || defined(AE_MASK_BLENDMODE_DARKEN) || defined(AE_LIP_BLENDMODE_DARKEN)
float BlendDarken(float base, float blend)
{
    return min(blend,base);
}

vec3 BlendDarken(vec3 base, vec3 blend)
{
    return vec3(BlendDarken(base.r,blend.r), BlendDarken(base.g,blend.g), BlendDarken(base.b,blend.b));
}

vec3 BlendDarken(vec3 base, vec3 blend, float opacity)
{
    return (BlendDarken(base, blend) * opacity + base * (1.0 - opacity));
}
#endif

#if defined(AE_HIGHLIGHT_BLENDMODE_DIFFERENCE) || defined(AE_SEQUIN_BLENDMODE_DIFFERENCE) || defined(AE_MASK_BLENDMODE_DIFFERENCE) || defined(AE_LIP_BLENDMODE_DIFFERENCE)
vec3 BlendDifference(vec3 base, vec3 blend)
{
    return abs(base - blend);
}

vec3 BlendDifference(vec3 base, vec3 blend, float opacity)
{
    return (BlendDifference(base, blend) * opacity + base * (1.0 - opacity));
}
#endif

#if defined(AE_HIGHLIGHT_BLENDMODE_EXCLUSION) || defined(AE_SEQUIN_BLENDMODE_EXCLUSION) || defined(AE_MASK_BLENDMODE_EXCLUSION) || defined(AE_LIP_BLENDMODE_EXCLUSION)
vec3 BlendExclusion(vec3 base, vec3 blend)
{
    return base + blend - 2.0 * base * blend;
}

vec3 BlendExclusion(vec3 base, vec3 blend, float opacity)
{
	return (BlendExclusion(base, blend) * opacity + base * (1.0 - opacity));
}
#endif

#if defined(AE_HIGHLIGHT_BLENDMODE_LIGHTEN) || defined(AE_SEQUIN_BLENDMODE_LIGHTEN) || defined(AE_MASK_BLENDMODE_LIGHTEN) || defined(AE_LIP_BLENDMODE_LIGHTEN)
float BlendLighten(float base, float blend)
{
    return max(blend,base);
}

vec3 BlendLighten(vec3 base, vec3 blend)
{
    return vec3(BlendLighten(base.r,blend.r), BlendLighten(base.g,blend.g), BlendLighten(base.b,blend.b));
}

vec3 BlendLighten(vec3 base, vec3 blend, float opacity)
{
    return (BlendLighten(base, blend) * opacity + base * (1.0 - opacity));
}
#endif

#if defined(AE_HIGHLIGHT_BLENDMODE_LINEARDODGE) || defined(AE_SEQUIN_BLENDMODE_LINEARDODGE) || defined(AE_MASK_BLENDMODE_LINEARDODGE) || defined(AE_LIP_BLENDMODE_LINEARDODGE)
float BlendLinearDodge(float base, float blend)
{
    return min(base + blend, 1.0);
}

vec3 BlendLinearDodge(vec3 base, vec3 blend)
{
    return min(base + blend, vec3(1.0));
}

vec3 BlendLinearDodge(vec3 base, vec3 blend, float opacity)
{
    return (BlendLinearDodge(base, blend) * opacity + base * (1.0 - opacity));
}
#endif

// blend mode of light color
vec3 HighlightBlend(vec3 base, vec3 blend, float alpha)
{
    blend = clamp(blend, 0.0, 1.0);
    vec3 color = mix(base, blend, alpha);
#ifdef AE_HIGHLIGHT_BLENDMODE_SCREEN
    color = BlendScreen(base, blend, alpha);
#endif
#ifdef AE_HIGHLIGHT_BLENDMODE_ADD
    color = BlendAdd(base, blend, alpha);
#endif
#ifdef AE_HIGHLIGHT_BLENDMODE_MULTIPLY
    color = BlendMultiply(base, blend, alpha);
#endif
#ifdef AE_HIGHLIGHT_BLENDMODE_OVERLAY
    color = BlendOverlay(base, blend, alpha);
#endif
#ifdef AE_HIGHLIGHT_BLENDMODE_SOFTLIGHT
    color = BlendSoftLight(base, blend, alpha);
#endif
#ifdef AE_HIGHLIGHT_BLENDMODE_AVERAGE
    color = BlendAverage(base, blend, alpha);
#endif
#ifdef AE_HIGHLIGHT_BLENDMODE_COLORBURN
    color = BlendColorBurn(base, blend, alpha);
#endif
#ifdef AE_HIGHLIGHT_BLENDMODE_COLORDODGE
    color = BlendColorDodge(base, blend, alpha);
#endif
#ifdef AE_HIGHLIGHT_BLENDMODE_DARKEN
    color = BlendDarken(base, blend, alpha);
#endif
#ifdef AE_HIGHLIGHT_BLENDMODE_DIFFERENCE
    color = BlendDifference(base, blend, alpha);
#endif
#ifdef AE_HIGHLIGHT_BLENDMODE_EXCLUSION
    color = BlendExclusion(base, blend, alpha);
#endif
#ifdef AE_HIGHLIGHT_BLENDMODE_LIGHTEN
    color = BlendLighten(base, blend, alpha);
#endif
#ifdef AE_HIGHLIGHT_BLENDMODE_LINEARDODGE
    color = BlendLinearDodge(base, blend, alpha);
#endif
    return color;
}

vec3 SequinBlend(vec3 base, vec3 blend, float alpha)
{
    blend = clamp(blend, 0.0, 1.0);
    vec3 color = mix(base, blend, alpha);
#ifdef AE_SEQUIN_BLENDMODE_SCREEN
    color = BlendScreen(base, blend, alpha);
#endif
#ifdef AE_SEQUIN_BLENDMODE_ADD
    color = BlendAdd(base, blend, alpha);
#endif
#ifdef AE_SEQUIN_BLENDMODE_MULTIPLY
    color = BlendMultiply(base, blend, alpha);
#endif
#ifdef AE_SEQUIN_BLENDMODE_OVERLAY
    color = BlendOverlay(base, blend, alpha);
#endif
#ifdef AE_SEQUIN_BLENDMODE_SOFTLIGHT
    color = BlendSoftLight(base, blend, alpha);
#endif
#ifdef AE_SEQUIN_BLENDMODE_AVERAGE
    color = BlendAverage(base, blend, alpha);
#endif
#ifdef AE_SEQUIN_BLENDMODE_COLORBURN
    color = BlendColorBurn(base, blend, alpha);
#endif
#ifdef AE_SEQUIN_BLENDMODE_COLORDODGE
    color = BlendColorDodge(base, blend, alpha);
#endif
#ifdef AE_SEQUIN_BLENDMODE_DARKEN
    color = BlendDarken(base, blend, alpha);
#endif
#ifdef AE_SEQUIN_BLENDMODE_DIFFERENCE
    color = BlendDifference(base, blend, alpha);
#endif
#ifdef AE_SEQUIN_BLENDMODE_EXCLUSION
    color = BlendExclusion(base, blend, alpha);
#endif
#ifdef AE_SEQUIN_BLENDMODE_LIGHTEN
    color = BlendLighten(base, blend, alpha);
#endif
#ifdef AE_SEQUIN_BLENDMODE_LINEARDODGE
    color = BlendLinearDodge(base, blend, alpha);
#endif
    return color;
}

// blend mode of base color --------------------------------------------------------------
vec3 MaskBlend(vec3 base, vec3 blend, float alpha)
{
    blend = clamp(blend, 0.0, 1.0);
    vec3 color = mix(base, blend, alpha);
#ifdef AE_MASK_BLENDMODE_SCREEN
    color = BlendScreen(base, blend, alpha);
#endif
#ifdef AE_MASK_BLENDMODE_ADD
    color = BlendAdd(base, blend, alpha);
#endif
#ifdef AE_MASK_BLENDMODE_MULTIPLY
    color = BlendMultiply(base, blend, alpha);
#endif
#ifdef AE_MASK_BLENDMODE_OVERLAY
    color = BlendOverlay(base, blend, alpha);
#endif
#ifdef AE_MASK_BLENDMODE_SOFTLIGHT
    color = BlendSoftLight(base, blend, alpha);
#endif
#ifdef AE_MASK_BLENDMODE_AVERAGE
    color = BlendAverage(base, blend, alpha);
#endif
#ifdef AE_MASK_BLENDMODE_COLORBURN
    color = BlendColorBurn(base, blend, alpha);
#endif
#ifdef AE_MASK_BLENDMODE_COLORDODGE
    color = BlendColorDodge(base, blend, alpha);
#endif
#ifdef AE_MASK_BLENDMODE_DARKEN
    color = BlendDarken(base, blend, alpha);
#endif
#ifdef AE_MASK_BLENDMODE_DIFFERENCE
    color = BlendDifference(base, blend, alpha);
#endif
#ifdef AE_MASK_BLENDMODE_EXCLUSION
    color = BlendExclusion(base, blend, alpha);
#endif
#ifdef AE_MASK_BLENDMODE_LIGHTEN
    color = BlendLighten(base, blend, alpha);
#endif
#ifdef AE_MASK_BLENDMODE_LINEARDODGE
    color = BlendLinearDodge(base, blend, alpha);
#endif
    return color;
}

// blend mode of enviroment
vec3 LipBlend(vec3 base, vec3 blend, float alpha)
{
    blend = clamp(blend, 0.0, 1.0);
    vec3 color = base * (1.0 - alpha) + blend * alpha;
#ifdef AE_LIP_BLENDMODE_SCREEN
    color = BlendScreen(base, blend, alpha);
#endif
#ifdef AE_LIP_BLENDMODE_ADD
    color = BlendAdd(base, blend, alpha);
#endif
#ifdef AE_LIP_BLENDMODE_MULTIPLY
    color = BlendMultiply(base, blend, alpha);
#endif
#ifdef AE_LIP_BLENDMODE_OVERLAY
    color = BlendOverlay(base, blend, alpha);
#endif
#ifdef AE_LIP_BLENDMODE_SOFTLIGHT
    color = BlendSoftLight(base, blend, alpha);
#endif
#ifdef AE_LIP_BLENDMODE_AVERAGE
    color = BlendAverage(base, blend, alpha);
#endif
#ifdef AE_LIP_BLENDMODE_COLORBURN
    color = BlendColorBurn(base, blend, alpha);
#endif
#ifdef AE_LIP_BLENDMODE_COLORDODGE
    color = BlendColorDodge(base, blend, alpha);
#endif
#ifdef AE_LIP_BLENDMODE_DARKEN
    color = BlendDarken(base, blend, alpha);
#endif
#ifdef AE_LIP_BLENDMODE_DIFFERENCE
    color = BlendDifference(base, blend, alpha);
#endif
#ifdef AE_LIP_BLENDMODE_EXCLUSION
    color = BlendExclusion(base, blend, alpha);
#endif
#ifdef AE_LIP_BLENDMODE_LIGHTEN
    color = BlendLighten(base, blend, alpha);
#endif
#ifdef AE_LIP_BLENDMODE_LINEARDODGE
    color = BlendLinearDodge(base, blend, alpha);
#endif
    return color;
}

#ifdef AE_NORMALTEX_ENABLE
mat3 GetRotation(vec3 vecAft)
{
    // vecBef = vec3(0.0, 0.0, 1.0)
    vec3 rotateAxis = normalize(vec3(-vecAft.y, vecAft.x, 0.0));
    float cosAngle = vecAft.z;
    float sinAngle = sin(acos(cosAngle));
    mat3 rotate;
    // Rodrigues' rotation formula
    rotate[0][0] = cosAngle + (1.0 - cosAngle) * rotateAxis.x * rotateAxis.x;
    rotate[0][1] = (1.0 - cosAngle) * rotateAxis.x * rotateAxis.y - sinAngle * rotateAxis.z;
    rotate[0][2] = (1.0 - cosAngle) * rotateAxis.x * rotateAxis.z + sinAngle * rotateAxis.y;
    rotate[1][0] = (1.0 - cosAngle) * rotateAxis.x * rotateAxis.y + sinAngle * rotateAxis.z;
    rotate[1][1] = cosAngle + (1.0 - cosAngle) * rotateAxis.y * rotateAxis.y;
    rotate[1][2] = (1.0 - cosAngle) * rotateAxis.y * rotateAxis.z - sinAngle * rotateAxis.x;
    rotate[2][0] = (1.0 - cosAngle) * rotateAxis.z * rotateAxis.x - sinAngle * rotateAxis.y;
    rotate[2][1] = (1.0 - cosAngle) * rotateAxis.y * rotateAxis.z + sinAngle * rotateAxis.x;
    rotate[2][2] = cosAngle + (1.0 - cosAngle) * rotateAxis.z * rotateAxis.z;
    return rotate;
}

vec3 GetNormal(vec3 normalBase, vec3 normalTex, float normalInt)
{
    mat3 rotate = GetRotation(normalBase);
    return normalize(mix(vec3(0.0, 0.0, 1.0), normalTex, normalInt) * rotate);
}
#endif

vec3 GetFresnel(float hov, vec3 F0)
{
    vec3 fresnel = F0 + (vec3(1.0) - F0) * pow((1.0 - hov), fresnelPow);
    return fresnel;
}

float GetDGGX(float noh, float roughness)
{
    float r2 = roughness * roughness;
    float r4 = r2 * r2;
    float nhGGX = noh * noh * (r4 - 1.0) + 1.0;
    nhGGX = max(nhGGX, 0.001);
    float D = r4 / (PI * nhGGX * nhGGX);
    return D;
}

float GetGSmith(float nov, float nol, float roughness)
{
    float r2 = roughness + 1.0;
    float r4 = r2 * r2 / 8.0;
    float nvSmith = nov / (nov * (1.0 - r4) + r4 + 0.001);
    float nlSmith = nol / (nol * (1.0 - r4) + r4 + 0.001);
    float G = nvSmith * nlSmith;
    return G;
}

vec3 GetHighlightBRDF(vec3 normalBase, vec3 normalTex, vec3 view, vec3 albedo)
{
#ifdef AE_NORMALTEX_ENABLE
    vec3 normal = GetNormal(normalBase, normalTex, uHighlightNormalInt);
#else
    vec3 normal = normalBase;
#endif
    vec3 light = normalize(-uHighlightDir);
    vec3 h = normalize(light + view);

    float nov = max(0.0, dot(normal, view));
    float nol = max(0.0, dot(normal, light));
    float noh = max(0.0, dot(normal, h));
    float hov = max(0.0, dot(h, view));
    float D = GetDGGX(noh, uHighlightRoughness);
    float G = GetGSmith(nov, nol, uHighlightRoughness);
    vec3 F0 = mix(vec3(F0Base), albedo, uHighlightMetallic);
    vec3 fresnel = GetFresnel(hov, F0);
    vec3 ks = fresnel;
    vec3 kd = (vec3(1.0) - uHighlightMetallic) * (1.0 - uHighlightMetallic);
    vec3 diffuse = albedo / PI * nol * kd;
    vec3 specular = D * G * fresnel;
    return (specular + diffuse) * uHighlightColor.rgb;
}

vec3 Square(vec3 v)
{
    return vec3(v.x * v.x, v.y * v.y, v.z * v.z);
}

// GGX / Trowbridge-Reitz
float D_GGX(float roughness, float NoH)
{
    float a = roughness * roughness;
    float a2 = a * a;
    float d = (NoH * a2 - NoH) * NoH + 1.0;
    return a2 / (PI * d * d);
}

// Smith term for GGX
float Vis_Smith(float roughness, float NoV, float NoL)
{
    float a = roughness * roughness;
    float a2 = a * a;

    float Vis_SmithV = NoV + sqrt(NoV * (NoV - NoV * a2) + a2);
    float Vis_SmithL = NoL + sqrt(NoL * (NoL - NoL * a2) + a2);
    return 1.0 / (Vis_SmithV * Vis_SmithL);
}

vec3 F_Fresnel(vec3 specular, float VoH)
{
    vec3 specularSqrt = sqrt(clamp(vec3(0, 0, 0), vec3(0.99, 0.99, 0.99), specular));
    vec3 n = (1.0 + specularSqrt) / (1.0 - specularSqrt);
    vec3 g = sqrt(n * n + VoH * VoH - 1.0);
    return 0.5 * Square((g - VoH) / (g + VoH)) * (1.0 + Square(((g + VoH) * VoH - 1.0) / ((g - VoH) * VoH + 1.0)));
}

vec3 GetSequinBRDF(vec3 normalBase, vec3 normalTex, vec3 light, vec3 specular) 
{
#ifdef AE_NORMALTEX_ENABLE
    vec3 normal = GetNormal(normalBase, normalTex, uSequinNormalInt);
#else
    vec3 normal = normalBase;
#endif
    vec3 view = normal;
    vec3 h = normalize(view + light);

    float VoH = dot(view, h);
    float NoV = dot(normal, view);
    float NoL = dot(normal, light);
    float NoH = dot(normal, h);
    float D = D_GGX(uSequinRoughness, NoH);
    vec3 F = F_Fresnel(specular, VoH);
    float V = Vis_Smith(uSequinRoughness, NoV, NoL);
    return F * V * D * clamp(dot(light, normal), 0.0, 1.0);
}

vec3 RGBtoHCV(vec3 rgb)
{
    vec4 p = (rgb.g < rgb.b) ? vec4(rgb.bg, -1.0, 2.0 / 3.0) : vec4(rgb.gb, 0.0, -1.0 / 3.0);
    vec4 q = (rgb.r < p.x) ? vec4(p.xyw, rgb.r) : vec4(rgb.r, p.yzx);

    float c = q.x - min(q.w, q.y);
    float h = abs((q.w - q.y) / (6.0 * c + 1e-7) + q.z);
    float v = q.x;

    return vec3(h, c, v);
}

vec3 RGBToHSL(vec3 rgb)
{
    vec3 hcv = RGBtoHCV(rgb);

    float lum = hcv.z - hcv.y * 0.5;
    float sat = hcv.y / (1.0 - abs(2.0 * lum - 1.0) + 1e-7);

    return vec3(hcv.x, sat, lum);
}

vec3 HUEtoRGB(float hue)
{
    float r = abs(6.0 * hue - 3.0) - 1.0;
    float g = 2.0 - abs(6.0 * hue - 2.0);
    float b = 2.0 - abs(6.0 * hue - 4.0);
    return clamp(vec3(r, g, b), 0.0, 1.0);
}

vec3 HSLToRGB(vec3 hsl)
{
    vec3 rgb = HUEtoRGB(hsl.x);
    float c = (1.0 - abs(2.0 * hsl.z - 1.0)) * hsl.y;
    rgb = (rgb - 0.5) * c + hsl.z;
    return rgb;
}

vec3 darkOpt(vec3 src, vec3 dst, float xth, float ymin)
{
    vec3 shsl = RGBToHSL(src.rgb);
    vec3 dhsl = RGBToHSL(dst.rgb);
    float w = ymin + (1.0 - ymin) * smoothstep(0.0, xth, shsl.b);

    float L = shsl.b * (1.0 - w) + dhsl.b * w;
    vec3 dst2 = HSLToRGB(vec3(dhsl.r, dhsl.g, L));
    return dst2;
}

// Enviroment-------------------------------------------------------------------
float Atan2(float x, float y)
{
    float signx = x < 0.0 ? -1.0 : 1.0;
    return signx * acos(clamp(y / length(vec2(x, y)), -1.0, 1.0));
}

vec2 DirToPanoramicTexCoords(vec3 reflDir, float rotation)
{
    vec2 uv;
    uv.x = Atan2(reflDir.x, -reflDir.z) - PI / 2.0;
    uv.y = acos(reflDir.y);
    uv = uv / vec2(2.0 * PI, PI);
    uv.x += rotation;
    uv.x = fract(uv.x + floor(uv.x) + 1.0);
    return uv;
}

vec3 IBLShading(vec3 normalBase, vec3 normalTex, vec3 viewDir, float envNormalInt, sampler2D envTexture, float rotation)
{
#ifdef AE_NORMALTEX_ENABLE
    vec3 normal = GetNormal(normalBase, normalTex, envNormalInt);
#else
    vec3 normal = normalBase;
#endif
    vec3 reflectDir = normalize(reflect(-viewDir, normal));
    vec2 uv = DirToPanoramicTexCoords(reflectDir, rotation);
    vec3 radiance = texture2D(envTexture, uv).rgb;
    return radiance;
}

vec3 GetLipEnvColor(vec3 normalBase, vec3 normalTex, vec3 viewDir)
{
    vec3 color = vec3(0.0);
    float alpha = texture2D(uUpperEnvMask, uv0).r;
    vec3 envColor = IBLShading(normalBase, normalTex, viewDir, uUpperEnvNormalInt, uUpperEnvTexture, uUpperEnvRotate);
    envColor *= alpha * uUpperEnvExposure;
    color += envColor.rgb;
    alpha = texture2D(uLowerEnvMask, uv0).r;
    envColor = IBLShading(normalBase, normalTex, viewDir, uLowerEnvNormalInt, uLowerEnvTexture, uLowerEnvRotate);
    envColor *= alpha * uLowerEnvExposure;
    color += envColor.rgb;
    return color;
}
// Enviroment----------------------------------------------------------------

float GetFaceSeg()
{
    float weight = 1.0;
#ifdef AE_FACESEG_ENABLE
    vec4 maskFace = texture2D(uFaceSeg, faceUV);
    float weightFace = maskFace.r;
    // 0.1, to avoid some basecase at the edge
    float uvFlagFace = 1.0 - step(0.1, faceUV.y);
    weightFace = max(uvFlagFace, weightFace);
    uvFlagFace = step(0.0, faceUV.x);
    float uvFlagFace2 = 1.0 - step(1.0, faceUV.x);
    weightFace = weightFace * uvFlagFace * uvFlagFace2;
    weightFace = max(weightFace, 1.0 - uFaceSegDetected);
    weight = min(weight, weightFace);
#endif
#ifdef AE_TEETHSEG_ENABLE
    vec4 maskTeeth = texture2D(uTeethSeg, teethUV);
    float weightTeeth = maskTeeth.r;
    float uvFlagTeeth = step(0.0, teethUV.x);
    float uvFlagTeeth2 = 1.0 - step(1.0, teethUV.x);
    weightTeeth = 1.0 - weightTeeth * uvFlagTeeth * uvFlagTeeth2;
    weightTeeth = max(weightTeeth, 1.0 - uTeethSegDetected);
    weight = min(weight, weightTeeth);
#endif
    return weight;
}

void main()
{
    vec4 srcColor = TextureFromFBO(uv1);
    if (normal0.x == 0.0 && normal0.y == 0.0 && normal0.z == 0.0) {
        gl_FragColor = srcColor;
        return;
    }

    vec3 baseColor = srcColor.rgb;

    if (u_enableMask > 0.5)
    {
        vec4 maskTex = texture2D(uMaskTexture, uv0) * uMaskOpacity;
#ifdef AE_MASK_USE_CUSTOM_COLOR
        maskTex.rgb = uMaskColor;
#else
        maskTex.rgb = clamp(maskTex.rgb / max(0.0001, maskTex.a), 0.0, 1.0);
#endif
        baseColor = MaskBlend(srcColor.rgb, maskTex.rgb, maskTex.a);
    }

    vec3 viewDir = normalize(u_WorldSpaceCameraPos - pos0);
    vec3 normalBase = normalize(mat3(uModel) * normal0);
    vec3 normalTex = vec3(0.0, 0.0, 1.0);
#ifdef AE_NORMALTEX_ENABLE
    normalTex = normalize((texture2D(uNormalTexture, uv0) * 2.0 - 1.0).rgb);
#endif

    vec3 finalColor = baseColor;
    vec3 lightColor = vec3(0.0);
    float lightOpacity = 0.0;

    if (u_enableSequin > 0.5)
    {
        vec3 specular = baseColor * mix(vec3(1.0), uSequinColor.rgb, uSequinMetallic);
        lightColor = GetSequinBRDF(normalBase, normalTex, normalize(uSequinPos - pos0), specular) * uSequinColor.a;
        lightOpacity = texture2D(uSequinMask, uv0).r * uSequinOpacity;
        lightColor = SequinBlend(finalColor, lightColor, lightOpacity);
        finalColor = darkOpt(finalColor, lightColor, 0.65, 0.4);
    }

    if (u_enableHighlight > 0.5)
    {
        lightColor = GetHighlightBRDF(normalBase, normalTex, viewDir, baseColor * uHighlightColor.rgb) * uHighlightColor.a;
        lightOpacity = texture2D(uHighlightMask, uv0).r * uHighlightOpacity;
        finalColor = HighlightBlend(finalColor, lightColor, lightOpacity);
    }

    if (u_enableLip > 0.5)
    {
        vec3 envColor = GetLipEnvColor(normalBase, normalTex, viewDir);
        finalColor = LipBlend(finalColor, envColor, 1.0 * uLipOpacity);
    }

    float segWeight = GetFaceSeg();
    finalColor = mix(srcColor.rgb, finalColor, uOpacity * segWeight);
    gl_FragColor = vec4(clamp(finalColor, 0.0, 1.0), 1.0) * srcColor.a;
}
