precision highp float;

attribute vec4 attPosition;
attribute vec2 attTexcoord0;
attribute vec3 attNormal;

uniform mat4 uMVP;
uniform mat4 uModel;

varying vec3 pos0;
varying vec2 uv0;
varying vec2 uv1;
varying vec3 normal0;

#ifdef AE_FACESEG_ENABLE
uniform mat4 uFaceSegMVP;
varying vec2 faceUV;
#define AE_SEG_ENABLE
#endif
#ifdef AE_TEETHSEG_ENABLE
uniform mat4 uTeethSegMVP;
varying vec2 teethUV;
#define AE_SEG_ENABLE
#endif

uniform vec4 u_ScreenParams; // built-in uniform

void main()
{
    gl_Position = uMVP * attPosition;
    pos0 = (uModel * attPosition).xyz;
    uv0 = attTexcoord0.xy;
    normal0 = attNormal.xyz;
    uv1 = gl_Position.xy / gl_Position.w * 0.5 + 0.5;

#ifdef AE_SEG_ENABLE
    vec2 screenPosition = vec2(uv1.x, 1.0 - uv1.y);
    screenPosition = screenPosition * u_ScreenParams.xy;
#endif
#ifdef AE_FACESEG_ENABLE
    faceUV = (uFaceSegMVP * vec4(screenPosition.xy, 0.0, 1.0)).xy;
#endif
#ifdef AE_TEETHSEG_ENABLE
    teethUV = (uTeethSegMVP * vec4(screenPosition.xy, 0.0, 1.0)).xy;
#endif
}
