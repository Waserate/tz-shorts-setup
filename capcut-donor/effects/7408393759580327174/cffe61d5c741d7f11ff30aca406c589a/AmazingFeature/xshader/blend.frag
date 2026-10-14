precision highp float;

varying highp vec2 uv0;

uniform sampler2D inputImageTexture;
uniform sampler2D blurImageTexture;
uniform sampler2D faceSkinMaskTexture;
uniform sampler2D lutImageTexture;

vec4 LUT8x8(vec4 inColor, sampler2D lutImageTexture)
{
    highp float blueColor = inColor.b * 63.0;
    
    highp vec2 quad1;
    quad1.y = floor(floor(blueColor) / 8.0);
    quad1.x = floor(blueColor) - (quad1.y * 8.0);
    highp vec2 quad2;
    quad2.y = floor(ceil(blueColor) / 8.0);
    quad2.x = ceil(blueColor) - (quad2.y * 8.0);
    
    highp vec2 texPos1 = vec2(quad1.xy * 0.125) + 0.5/512.0 + ((0.125 - 1.0/512.0) * inColor.rg);
    highp vec2 texPos2 = vec2(quad2.xy * 0.125) + 0.5/512.0 + ((0.125 - 1.0/512.0) * inColor.rg);
    
    lowp vec4 newColor2_1 = texture2D(lutImageTexture, texPos1);
    lowp vec4 newColor2_2 = texture2D(lutImageTexture, texPos2);

    lowp vec4 newColor22 = mix(newColor2_1, newColor2_2, fract(blueColor));

    return newColor22;
}

void main()
{
    float dark_threshold_Factor = 28.86751;

    vec4 srcColor = texture2D(inputImageTexture, uv0); 
    vec4 blurColor = texture2D(blurImageTexture, uv0); 
    vec4 maskColor = texture2D(faceSkinMaskTexture, uv0);

    vec4 dstColor = vec4(srcColor.rgb, blurColor.a);    //to pass over variance

    if (maskColor.b > 0.005) {
        lowp float cDistance = distance(vec3(0.0, 0.0, 0.0), max(blurColor.rgb - srcColor.rgb, 0.0)) * dark_threshold_Factor; 
        if(cDistance > 0.5 && cDistance < 5.0) { 
            // src: 0.5->5.0, dst: 0.4->0.8
            vec4 brightColor = LUT8x8(srcColor, lutImageTexture);
            dstColor.rgb = mix(srcColor.rgb, brightColor.rgb, maskColor.b * (0.0889 * cDistance + 0.355));
        }
    }

    gl_FragColor = dstColor;
}