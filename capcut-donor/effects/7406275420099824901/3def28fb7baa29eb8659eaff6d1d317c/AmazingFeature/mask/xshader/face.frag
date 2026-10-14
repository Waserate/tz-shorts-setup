precision highp float;

varying vec2 uv0;
varying vec2 uv_face_0;
varying vec2 uv_face_1;
varying vec2 uv_face_2;
varying vec2 uv_face_3;
varying vec2 uv_face_4;


uniform vec4 u_baseColor;

uniform int faceCount;

uniform sampler2D makeupTexture;
uniform sampler2D inputTexture;
uniform sampler2D maskTexture0;
uniform sampler2D maskTexture1;
uniform sampler2D maskTexture2;
uniform sampler2D maskTexture3;
uniform sampler2D maskTexture4;

void main() {
    vec4 src = texture2D(inputTexture, uv0);
    vec4 makeup = texture2D(makeupTexture, uv0);


    float weight = 0.0;
    if (faceCount> 0)
    {
        if (clamp(uv_face_0, 0.0, 1.0) == uv_face_0)
        {

            vec4 mask = texture2D(maskTexture0, vec2(uv_face_0.x, uv_face_0.y));
            weight = max(weight, mask.r);
        }
    }
    
    if (faceCount> 1)
    {
        if (clamp(uv_face_1, 0.0, 1.0) == uv_face_1)
        {
            vec4 mask = texture2D(maskTexture1, vec2(uv_face_1.x, uv_face_1.y));
            weight = max(weight, mask.r);
        }
    }
    if (faceCount> 2)
    {
        if (clamp(uv_face_2, 0.0, 1.0) == uv_face_2)
        {
            vec4 mask = texture2D(maskTexture2, vec2(uv_face_2.x, uv_face_2.y));
            weight = max(weight, mask.r);
        }
    }

    if (faceCount> 3)
    {
        if (clamp(uv_face_3, 0.0, 1.0) == uv_face_3)
        {
            vec4 mask = texture2D(maskTexture3, vec2(uv_face_3.x, uv_face_3.y));
            weight = max(weight, mask.r);
        }
    }
    if (faceCount> 4)
    {
        if (clamp(uv_face_4, 0.0, 1.0) == uv_face_4)
        {
            vec4 mask = texture2D(maskTexture4, vec2(uv_face_4.x, uv_face_4.y));
            weight = max(weight, mask.r);
        }
    }
    
    // gl_FragColor = mix(vec4(0.0), vec4(1.0, 0.0 , 0.0, 1.0),  weight);
    gl_FragColor = mix(src, makeup, weight);
}
