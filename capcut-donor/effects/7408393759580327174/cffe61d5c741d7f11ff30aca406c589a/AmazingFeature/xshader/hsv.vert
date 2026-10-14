precision highp float;

attribute vec3 position;
attribute vec2 texcoord0;
varying vec2 uv0;
varying vec2 skinUV;

void main() 
{
    gl_Position = vec4(position.xyz, 1.0);
    uv0 = texcoord0;
    skinUV = vec2(uv0.x, 1.0 - uv0.y);    
}
