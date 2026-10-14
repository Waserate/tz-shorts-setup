precision highp float;
varying vec2 uv;
varying vec2 uv_screen;

// uniform sampler2D u_flow;
uniform sampler2D u_gan;

uniform sampler2D u_input;

uniform mat4 u_mvpMat;
uniform mat4 u_mvpMat_rev;

uniform sampler2D u_blurmask;
uniform float u_h;

void main() {
  // magnify the intensity for better visualization
  float mask = texture2D(u_blurmask, uv).r;
  vec4 gan = texture2D(u_gan, uv);
  vec4 src = texture2D(u_input, uv_screen);
  gan.a *= mask;

  gl_FragColor = vec4(mix(src.rgb, gan.rgb, gan.a), src.a * mask);
}
