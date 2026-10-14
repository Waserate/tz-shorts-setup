#version 300 es
precision highp float;

in vec3 attPosition;
in vec2 attUV;

out vec2 uv0;

void main() {
    gl_Position = vec4(attPosition,1.0);
    uv0 = attUV.xy;
}
