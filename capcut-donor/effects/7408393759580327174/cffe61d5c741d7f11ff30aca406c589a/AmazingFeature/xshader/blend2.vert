precision highp float;

attribute vec3 position;
attribute vec2 texcoord0;
varying vec2 uv;
varying highp vec2 uv0;

void main() 
{ 
    gl_Position = vec4(position.xyz, 1.0);
    uv = texcoord0;
    uv0 = vec2(texcoord0.x, 1.0 - texcoord0.y);
}

