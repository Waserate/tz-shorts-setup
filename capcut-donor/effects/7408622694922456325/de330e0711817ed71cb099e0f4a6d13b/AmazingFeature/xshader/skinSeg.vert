precision highp float;
attribute vec3 attPosition;
attribute vec2 attTexcoord0;
varying vec2 texcoord1;
void main ()
{
    vec4 homogeneous_pos = vec4(attPosition, 1.0);
    texcoord1 = vec2(attTexcoord0.x,  attTexcoord0.y);
    gl_Position = homogeneous_pos;
}
