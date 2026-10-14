precision mediump float;

varying highp vec2 uv0;

uniform sampler2D inputImageTexture;
uniform sampler2D faceSkinMaskTexture;
uniform float valueFactor;

uniform float widthOffset;
uniform float heightOffset;


vec4 processing_1pixel(vec4 sum_value, float center_gray, vec2 coor) {
    lowp vec3 tmp_color = texture2D(inputImageTexture, coor).rgb;
    lowp float tmp_value_dis = tmp_color.g - center_gray;
    tmp_value_dis = 1. - min(tmp_value_dis * tmp_value_dis * valueFactor, 1.);
    sum_value.xyz += tmp_color * tmp_value_dis;
    sum_value.w += tmp_value_dis;
    return sum_value;
}

void main(void)
{
    lowp vec3 centerColor = texture2D(inputImageTexture, uv0).rgb;
    lowp float skinArea = texture2D(faceSkinMaskTexture, uv0).a;
    
    lowp vec3 resColor = centerColor;

    if (skinArea > 0.1) {

        ////
        highp vec2 textureShift1[4];
        highp vec2 textureShift2[4];
        highp vec2 textureShift3[4];

        vec2 unit_uv = 0.45 * vec2(widthOffset, heightOffset);

        float scale = 0.6;
        vec2 offset = scale * unit_uv;

        // circle 1
        textureShift1[0] = offset * vec2(5, 0);
        textureShift1[1] = offset * vec2(0, 5);
        textureShift1[2] = offset * vec2(3, 4);
        textureShift1[3] = offset * vec2(4, 3);

        // circle 2
        textureShift2[0] = offset * vec2(10, 0);
        textureShift2[1] = offset * vec2(0, 10);
        textureShift2[2] = offset * vec2(6, 8);
        textureShift2[3] = offset * vec2(8, 6);

        scale = 1.0;
        offset = scale * unit_uv; 

        // circle 3
        textureShift3[0] = offset * vec2(20, 0);
        textureShift3[1] = offset * vec2(0, 20);
        textureShift3[2] = offset * vec2(12, 16);
        textureShift3[3] = offset * vec2(16, 12);
        ////

        lowp float center_gray = centerColor.g;

        mediump vec4 sum_value = vec4(0., 0., 0., 0.);

        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift1[0].x, textureShift1[0].y));  //5 0
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(-textureShift1[0].x, textureShift1[0].y)); //-5 0
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift1[1].x, textureShift1[1].y));  //0 5
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift1[1].x, -textureShift1[1].y)); //0 -5
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift1[2].x, textureShift1[2].y));  //3 4
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(-textureShift1[2].x, textureShift1[2].y));  //-3 4
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift1[2].x, -textureShift1[2].y));  //3 -4
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(-textureShift1[2].x, -textureShift1[2].y));  //-3 -4
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift1[3].x, textureShift1[3].y));  //4 3
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(-textureShift1[3].x, textureShift1[3].y));  //-4 3
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift1[3].x, -textureShift1[3].y));  //4 -3
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(-textureShift1[3].x, -textureShift1[3].y));  //-4 -3


        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift2[0].x, textureShift2[0].y));  //10 0
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(-textureShift2[0].x, textureShift2[0].y)); //-10 0
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift2[1].x, textureShift2[1].y));  //0 10
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift2[1].x, -textureShift2[1].y)); //0 -10
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift2[2].x, textureShift2[2].y));  //6 8
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(-textureShift2[2].x, textureShift2[2].y));  //-6 8
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift2[2].x, -textureShift2[2].y));  //6 -8
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(-textureShift2[2].x, -textureShift2[2].y));  //-6 -8
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift2[3].x, textureShift2[3].y));  //8 6
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(-textureShift2[3].x, textureShift2[3].y));  //-8 6
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift2[3].x, -textureShift2[3].y));  //8 -6
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(-textureShift2[3].x, -textureShift2[3].y));  //-8 -6


        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift3[0].x, textureShift3[0].y));  //20 0
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(-textureShift3[0].x, textureShift3[0].y)); //-20 0
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift3[1].x, textureShift3[1].y));  //0 20
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift3[1].x, -textureShift3[1].y)); //0 -20
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift3[2].x, textureShift3[2].y));  //12 16
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(-textureShift3[2].x, textureShift3[2].y));  //-12 16
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift3[2].x, -textureShift3[2].y));  //12 -16
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(-textureShift3[2].x, -textureShift3[2].y));  //-12 -16
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift3[3].x, textureShift3[3].y));  //16 12
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(-textureShift3[3].x, textureShift3[3].y));  //-16 12
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(textureShift3[3].x, -textureShift3[3].y));  //16 -12
        sum_value = processing_1pixel(sum_value, center_gray, uv0 + vec2(-textureShift3[3].x, -textureShift3[3].y));  //-16 -12

        sum_value.xyz += centerColor;
        sum_value.w += 1.0;

        resColor =  sum_value.xyz / sum_value.w;
    }
    
    gl_FragColor = vec4(resColor, 1.0);
}

