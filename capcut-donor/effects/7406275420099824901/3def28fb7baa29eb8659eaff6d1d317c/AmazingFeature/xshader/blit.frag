precision highp float;
varying vec2 uv0;
uniform sampler2D blitTexture;

void main ()
{
    gl_FragColor = texture2D(blitTexture, uv0);
}