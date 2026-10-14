precision highp float;

varying highp vec2 uv;
varying highp vec2 uv0;

uniform sampler2D inputImageTexture;
uniform sampler2D blendImageTexture;
uniform sampler2D blur3ImageTexture;
uniform sampler2D blur4ImageTexture;
uniform sampler2D faceSkinMaskTexture;
uniform sampler2D skinsegMaskTexture;

const float theta = 0.5;                            //adjustable (the smaller, the more structured)

void main(void)
{
    vec4 oriColor = texture2D(inputImageTexture, uv).rgba;
    vec4 preColor = texture2D(blendImageTexture, uv).rgba;     //note: alpha channel contains the variance
    vec4 blurColor = texture2D(blur3ImageTexture, uv).rgba;
    vec4 twiceBlurColor = texture2D(blur4ImageTexture, uv).rgba;
    vec4 maskColor = texture2D(faceSkinMaskTexture, uv).rgba; //note: alpha channel contains the green channel inside face, and the skin seg mask outside face

    vec4 skinColor = texture2D(skinsegMaskTexture, uv0);

    lowp float kMin = 1.0 - preColor.a / (preColor.a + theta);

    //take effect on the blue channel inside face, and take effect on the skinseg mask outside face
    lowp float smoothArea = mix(skinColor.a, maskColor.b, step(0.005, maskColor.g)) * skinColor.a * kMin;
    lowp float smoothIntensity = maskColor.a;

    // step 1. apply image with "substraction mode", by params (scale 2.0, compensation 128), and then apply linearLight blend mode
    vec3 hColor = (preColor.rgb - blurColor.rgb) / 2.0 + 0.5;
    vec3 evenColor = clamp(twiceBlurColor.rgb + 2.0 * hColor.rgb - 1.0, vec3(0.0), vec3(1.0));

    evenColor = mix(preColor.rgb, evenColor.rgb, smoothArea);

    // step 2: add smooth
    lowp float smoothFactor = mix(0.3, smoothIntensity-0.3, step(0.6, smoothIntensity));
    evenColor = mix(evenColor.rgb, twiceBlurColor.rgb, smoothFactor * smoothArea);

    // ## smooth output
    lowp float finalIntensity = mix(smoothIntensity * 1.67, 1.0, step(0.6, smoothIntensity));
    lowp vec3 smoothColor = mix(oriColor.rgb, evenColor.rgb, finalIntensity);

    gl_FragColor = vec4(smoothColor, oriColor.a);

}