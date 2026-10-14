precision mediump float;
varying highp vec2 textureCoordinate;

uniform sampler2D inputImageMaskTexture;

void main() {
    lowp vec3 faceMask = texture2D(inputImageMaskTexture, textureCoordinate).rgb; 
    gl_FragColor = vec4(faceMask.b, faceMask.g, 0., 0.); //RG
}