precision mediump float;
varying highp vec2 textureCoordinate[9];

uniform sampler2D _MainTex;
#define argba _MainTex
uniform sampler2D faceMask;
uniform sampler2D newGradimage;

uniform float clearIntensity;

vec3 LUT8x8(vec3 inColor, sampler2D lutImageTexture)
{
    highp float blueColor = inColor.b * 63.0;
    
    highp vec2 quad1;
    quad1.y = floor(floor(blueColor) / 8.0);
    quad1.x = floor(blueColor) - (quad1.y * 8.0);
    highp vec2 quad2;
    quad2.y = floor(ceil(blueColor) / 8.0);
    quad2.x = ceil(blueColor) - (quad2.y * 8.0);
    
    highp vec2 texPos1 = (quad1.xy * 0.125) + 0.5/512.0 + ((0.125 - 1.0/512.0) * inColor.rg);
    highp vec2 texPos2 = (quad2.xy * 0.125) + 0.5/512.0 + ((0.125 - 1.0/512.0) * inColor.rg);
    
    lowp vec3 newColor2_1 = texture2D(lutImageTexture, texPos1).rgb;
    lowp vec3 newColor2_2 = texture2D(lutImageTexture, texPos2).rgb;

    lowp vec3 newColor22 = mix(newColor2_1, newColor2_2, fract(blueColor));

    return newColor22;
}

void main() 
{
    vec4 inputColor = texture2D(argba, textureCoordinate[4]);

    vec4 dstColor = inputColor;

    if (clearIntensity > 0.0) {
        vec3 centervalue = texture2D(newGradimage, textureCoordinate[4]).rgb;
        float avgDiff = 0.04 * centervalue.b;
        avgDiff += 0.16 * texture2D(newGradimage, textureCoordinate[0]).b;
        avgDiff += 0.08 * texture2D(newGradimage, textureCoordinate[1]).b;
        avgDiff += 0.16 * texture2D(newGradimage, textureCoordinate[2]).b;
        avgDiff += 0.08 * texture2D(newGradimage, textureCoordinate[3]).b;
        avgDiff += 0.08 * texture2D(newGradimage, textureCoordinate[5]).b;
        avgDiff += 0.16 * texture2D(newGradimage, textureCoordinate[6]).b;
        avgDiff += 0.08 * texture2D(newGradimage, textureCoordinate[7]).b;
        avgDiff += 0.16 * texture2D(newGradimage, textureCoordinate[8]).b;

        float maskratio = (1.0 - 0.4 * texture2D(faceMask, textureCoordinate[4]).g);

        float lastgrad = centervalue.r;
        lastgrad = (lastgrad - 0.5) / 4.0;

        vec3 sharpColor = clamp(dstColor.rgb + vec3(avgDiff * 1.35 * lastgrad), 0.0, 1.0);
        dstColor.rgb = mix(dstColor.rgb, sharpColor, clearIntensity * maskratio);
    }

    gl_FragColor = dstColor;
}