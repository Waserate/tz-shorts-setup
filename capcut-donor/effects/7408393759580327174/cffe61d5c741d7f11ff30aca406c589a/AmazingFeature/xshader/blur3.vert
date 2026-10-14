precision highp float;

attribute vec3 position;
attribute vec2 texcoord0;
varying vec2 uv0;


void main()
{
    gl_Position = vec4(position, 1.0);
    uv0 = texcoord0;
}