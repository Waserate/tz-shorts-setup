precision highp float;
varying highp vec2 uv0;
varying vec2 skinUV;
uniform sampler2D u_albedo;

uniform sampler2D inputImageTexture; //src image
uniform sampler2D skinsegMaskTexture; //skin
uniform sampler2D faceMaskTexture; //face mask
uniform float skinIntensity; 
uniform float hasFaceFlag;

vec3 rgb2hsv(lowp vec3 c) { 
    vec4 K = vec4(0.0, -0.33333, 0.66667, -1.0); 
    highp vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g)); 
    highp vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r)); 
    highp float d = q.x - min(q.w, q.y); 
    highp float e = 1.0e-10; 
    float s = 0.0; 
    vec3 hsv = vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), s, q.x); 
    return hsv; 
}

void main()
{
    lowp vec3 srcColor = texture2D(inputImageTexture, uv0).rgb; 
    lowp float skinColorAlpha = texture2D(skinsegMaskTexture, skinUV).a;

    vec3 hsvSpace = rgb2hsv(srcColor.rgb);

    lowp float opacity = 1.0;  // auto segmentation offer to hsv color space
    if ((0.1 <= hsvSpace.x && hsvSpace.x <= 0.89) || hsvSpace.z <= 0.3) { 
        opacity = 0.0;
    }
    if (0.3 < hsvSpace.z && hsvSpace.z < 0.32) { 
        opacity = min(opacity, (0.32 - hsvSpace.z) * 50.0);
    }

    // case 1: when smash could detected face, we 
    if (hasFaceFlag > 0.0) {

        lowp vec4 faceMask = texture2D(faceMaskTexture, uv0).rgba;

        // after hsv operation, add more prohibited area to Blue-channel
        lowp vec3 resColor = vec3(faceMask.r, faceMask.g, min(faceMask.b, opacity));

        // the face area refers to the facelandmark mask, the other skin area refers to the skinseg mask
        lowp float skinArea = mix(skinColorAlpha * skinIntensity, faceMask.g * faceMask.a, step(0.1, faceMask.g));

        // the Alpha-channel is where the skin area lies
        gl_FragColor = vec4(vec3(resColor), skinArea);

    } else { 
        // case 2: when no face detected, we use the result of the skin seg algorithm

        // the Blue-channle and Alpha-channel is where the skin area lies
        gl_FragColor = vec4(vec3(0.0, 0.0, skinColorAlpha), skinColorAlpha * skinIntensity);
    }

}
