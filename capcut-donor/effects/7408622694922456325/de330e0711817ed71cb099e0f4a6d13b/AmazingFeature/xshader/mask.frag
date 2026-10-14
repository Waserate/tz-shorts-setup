precision highp float;
varying vec2 sucaiTexCoord;
uniform sampler2D sucaiImageTexture;

void main(void)
{
    vec4 sucai = texture2D(sucaiImageTexture, sucaiTexCoord);
    gl_FragColor = sucai;
}
