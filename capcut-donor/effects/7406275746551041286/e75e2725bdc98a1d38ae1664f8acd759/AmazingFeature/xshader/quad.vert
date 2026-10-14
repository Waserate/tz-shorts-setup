precision highp float;
attribute vec3 position;
attribute vec2 texcoord0;
varying vec2 uv;
varying vec2 uv_screen;
uniform mat4 u_mvpMat;

void main() {
  vec4 pos = vec4(position.xy, 0.0, 1.0);
  gl_Position = u_mvpMat * pos;
  uv = texcoord0;
  uv_screen = gl_Position.xy / gl_Position.w * 0.5 + 0.5;
}