precision mediump float;
varying highp vec2 textureCoordinate[9];

uniform sampler2D _MainTex;
#define srcTex _MainTex
uniform sampler2D lastGradimage;

uniform float frameindex;


float Gao(float a)
{
    return (step(2.5 / 255.0, abs(a)) * 0.7 + 0.3);     //0.3~0.7
}


void main() 
{
    
    float a0, a1, a2, a3, a4, a5, a6, a7, a8;
    float grad;
    float Gaodiff;
    a0 = texture2D(srcTex, textureCoordinate[0]).g;
    a1 = texture2D(srcTex, textureCoordinate[1]).g;
    a2 = texture2D(srcTex, textureCoordinate[2]).g;
    a3 = texture2D(srcTex, textureCoordinate[3]).g;
    a4 = texture2D(srcTex, textureCoordinate[4]).g;
    a5 = texture2D(srcTex, textureCoordinate[5]).g;
    a6 = texture2D(srcTex, textureCoordinate[6]).g;
    a7 = texture2D(srcTex, textureCoordinate[7]).g;
    a8 = texture2D(srcTex, textureCoordinate[8]).g;

    float sum = a4 * 0.04;
    sum += a0 * 0.16;
    sum += a1 * 0.08;
    sum += a2 * 0.16;
    sum += a3 * 0.08;
    sum += a5 * 0.08;
    sum += a6 * 0.16;
    sum += a7 * 0.08;
    sum += a8 * 0.16;
    float diff = a4 - sum;
    grad = diff;
    Gaodiff = Gao(diff);


    float fuhao = sign(grad);   //-1,0,1
    const float decay = 0.333 * 255.0;
    grad = 2.5 * (log(1.0 + decay * abs(grad))) / decay * fuhao;

    vec2 lastgrad = texture2D(lastGradimage, textureCoordinate[4]).rg;
    float reallast = (lastgrad.r - 0.5) / 4.0;
    float laoshigrad = grad;
    if(frameindex > 0.98)
        grad = 0.05 * grad + 0.95 * reallast;

    float absImageDiff = 0.04 * abs(a4 - lastgrad.g); 
    absImageDiff += 0.16 * abs(a0 - texture2D(lastGradimage, textureCoordinate[0]).g);
    absImageDiff += 0.08 * abs(a1 - texture2D(lastGradimage, textureCoordinate[1]).g);
    absImageDiff += 0.16 * abs(a2 - texture2D(lastGradimage, textureCoordinate[2]).g);
    absImageDiff += 0.08 * abs(a3 - texture2D(lastGradimage, textureCoordinate[3]).g);
    absImageDiff += 0.08 * abs(a5 - texture2D(lastGradimage, textureCoordinate[5]).g);
    absImageDiff += 0.16 * abs(a6 - texture2D(lastGradimage, textureCoordinate[6]).g);
    absImageDiff += 0.08 * abs(a7 - texture2D(lastGradimage, textureCoordinate[7]).g);
    absImageDiff += 0.16 * abs(a8 - texture2D(lastGradimage, textureCoordinate[8]).g);
    
    const float tolerate = 11.0 / 255.0;
    float weight = min(absImageDiff / tolerate, 1.0);
    grad = mix(grad, laoshigrad, weight);
    
    gl_FragColor = vec4(grad * 4.0 + 0.5, a4, Gaodiff, 0.);   //store to RGB
}