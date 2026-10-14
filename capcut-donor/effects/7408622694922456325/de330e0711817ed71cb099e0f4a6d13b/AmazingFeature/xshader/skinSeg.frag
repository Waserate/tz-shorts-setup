precision highp float; 

uniform sampler2D inputTexture;
uniform sampler2D ganTexture;
uniform sampler2D filterBgTexture;
uniform sampler2D filterSkinTexture;
uniform sampler2D u_AlbedoTexture;   //mask
varying vec2 texcoord1; 
uniform float intensity;

//-- -- -- -- -- -- -- -- -- -- -- --
uniform sampler2D lut_max;
uniform sampler2D lut_min;

uniform float coldWarmIntensity;
//-- -- -- -- -- -- -- -- -- -- -- --

//softblend
float blendSoftLight(float base, float blend) {
    return (blend < 0.5) ? (2.0 * base * blend + base * base * (1.0 - 2.0 * blend)) : (sqrt(base) * (2.0 * blend - 1.0) + 2.0 * base * (1.0 - blend));
}

vec3 blendSoftLight(vec3 base, vec3 blend) {
    return vec3(blendSoftLight(base.r, blend.r), blendSoftLight(base.g, blend.g), blendSoftLight(base.b, blend.b));
}

//adjust skin
//                  origin picture     min lut        max lut            intensity
vec4 filterFun(vec4 baseColor, sampler2D minTex, sampler2D maxTex, float intensity)
{   
    float slider_progress = abs(intensity);  //absolute value of intensity

    vec4 curColor = baseColor;   //origin picture
    vec4 textureColor = curColor;  //origin picture

    //This part is get value from lut
    float blueColor = curColor.b * (17.0 - 1.0);  
    vec2 standardTableSize = vec2(289.0, 17.0);
    vec2 pixelSize = 1.0 / standardTableSize;
    vec2 quad1 = vec2(0.0);
    quad1.y = floor(floor(blueColor) / 17.0);
    quad1.x = floor(blueColor) - (quad1.y * 1.0);
    vec2 quad2;
    quad2.y = floor(ceil(blueColor) / 17.0);
    quad2.x = ceil(blueColor) - (quad2.y * 1.0);
    vec2 texPos1;
    texPos1.x = (quad1.x * 1.0 / 17.0) + 0.5 / standardTableSize.x + ((1.0 / 17.0 - 1.0 / standardTableSize.x) * textureColor.r);
    texPos1.y = (quad1.y * 1.0 / 1.0) + 0.5 / standardTableSize.y +((1.0 / 1.0 - 1.0 / standardTableSize.y) * textureColor.g);
    vec2 texPos2;
    texPos2.x = (quad2.x * 1.0 / 17.0) + 0.5 / standardTableSize.x + ((1.0 / 17.0 - 1.0 / standardTableSize.x) * textureColor.r);
    texPos2.y = (quad2.y * 1.0 / 1.0) + 0.5 / standardTableSize.y +((1.0 / 1.0 - 1.0 / standardTableSize.y) * textureColor.g);
    float alpha = fract(blueColor);

    vec4 newColor = vec4(0.0);
    if (intensity < 0.0){   //choose different lut picture for negative and positive intensities
        //if < 0.0，use minTex
        vec4 newColor1 = texture2D(minTex, texPos1);
        vec4 newColor2 = texture2D(minTex, texPos2);
        newColor = mix(newColor1, newColor2, alpha);
    } else {
        //if > 0.0，use maxTex
        vec4 newColor1 = texture2D(maxTex, texPos1);
        vec4 newColor2 = texture2D(maxTex, texPos2);
        newColor = mix(newColor1, newColor2, alpha);
    }
    newColor = mix(curColor,newColor,slider_progress);   //use absolute value of intensity to mix，
    return newColor;
}

void main() {
    highp vec4 textureColor1 = texture2D(inputTexture, texcoord1);
    float inputImageAlpha = textureColor1.a;
    textureColor1 = clamp(textureColor1, 0.0, 1.0);
    
    highp float blueColor = textureColor1.b * 63.0;
    
    highp vec2 quad1;
    quad1.y = floor(floor(blueColor) / 8.0);
    quad1.x = floor(blueColor) - (quad1.y * 8.0);

    highp vec2 texPos1 = (quad1.xy * 0.125) + 0.5/512.0 + ((0.125 - 1.0/512.0) * textureColor1.rg);

    lowp vec4 newColor12 = texture2D(filterBgTexture, texPos1);
    lowp vec4 newColor22 = texture2D(filterSkinTexture, texPos1);

    vec2 maskCoord = vec2(texcoord1.x, 1.0 - texcoord1.y);
    float mask = texture2D(ganTexture, maskCoord).a;

    vec3 final = mix(newColor12.rgb, newColor22.rgb, mask);  //skin color after adjust 
    vec4 resultTemp = vec4(mix(textureColor1.rgb, final.rgb, intensity), 1.0);   //skin transform result

    //-- -- -- --The above part finished skin transform, could follow the above logic to modify coldWarm-- -- -- -- 
    
    // Xingtu's logic 0-1
    //input coldWarmIntensity range [0 -1]
    //float cwIntensity = 2.0 * coldWarmIntensity - 1.0;  //intensity mapping
    //
    // Jianying's input coldWarmIntensity range [-0.5,0.5]
    float cwIntensity = 2.0 * coldWarmIntensity;  //intensity mapping
    //cwIntensity range[-0.2, 0.3]
    if(cwIntensity < 0.0)
        cwIntensity = cwIntensity *0.2;
    else
        cwIntensity = cwIntensity* 0.3;
    //may need normalize
    //...
    //
    vec4 result = filterFun(resultTemp, lut_min, lut_max, cwIntensity * mask);  //add 
    // -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 

    //This part add Contour(xiurong)
    vec4 tex = texture2D(u_AlbedoTexture, texcoord1);  //Contour(xiurong) mask

    vec4 dst = vec4(blendSoftLight(result.rgb, clamp(tex.rgb / tex.a, 0., 1.)), 1.);  //a middle variable
    dst = mix(result, dst, tex.a);   //Two step process Contour result， First step : blend

    float xiurongIntensity = 0.15 * intensity;
    result =  mix(result, dst, xiurongIntensity);  //Second step blend get result

    //gl_FragColor = vec4(result.rgb, 1.);
    gl_FragColor = vec4(result.rgb, inputImageAlpha);
}