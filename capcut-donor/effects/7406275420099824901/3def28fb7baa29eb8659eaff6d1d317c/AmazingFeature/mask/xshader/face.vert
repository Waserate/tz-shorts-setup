precision highp float;


attribute vec3 position;
attribute vec4 color;
attribute vec2 texcoord0;

uniform vec4 u_ScreenParams; // built-in uniform
uniform mat4 u_MVP_0;
uniform mat4 u_MVP_1;
uniform mat4 u_MVP_2;
uniform mat4 u_MVP_3;
uniform mat4 u_MVP_4;

varying vec2 uv0;
varying vec2 uv_face_0;
varying vec2 uv_face_1;
varying vec2 uv_face_2;
varying vec2 uv_face_3;
varying vec2 uv_face_4;


void main() {
    gl_Position = vec4(position.xy, 0.0, 1.0);

    vec2 screen_position = (position.xy + 1.0) / 2.0;
    screen_position = vec2(screen_position.x, 1.0 - screen_position.y);
    screen_position = screen_position * u_ScreenParams.xy;

    uv0 = texcoord0;  // original image
    uv_face_0 = (u_MVP_0 * vec4(screen_position.xy, 0.0, 1.0)).xy;
    uv_face_1 = (u_MVP_1 * vec4(screen_position.xy, 0.0, 1.0)).xy;
    uv_face_2 = (u_MVP_2 * vec4(screen_position.xy, 0.0, 1.0)).xy;
    uv_face_3 = (u_MVP_3 * vec4(screen_position.xy, 0.0, 1.0)).xy;
    uv_face_4 = (u_MVP_4 * vec4(screen_position.xy, 0.0, 1.0)).xy;
}