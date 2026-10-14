#version 300 es
precision highp float;
in highp vec2 uv0;
out vec4 outColor;

#define MAX_POINTS 25*3
uniform vec2 controlPoints[MAX_POINTS];
uniform int pointsNums;


vec2 getControlPoints(int index)
{
    vec2 res = vec2(0.0);
    switch (index) {
        case 0: res = controlPoints[0]; break;
        case 1: res = controlPoints[1]; break;
        case 2: res = controlPoints[2]; break;
        case 3: res = controlPoints[3]; break;
        case 4: res = controlPoints[4]; break;
        case 5: res = controlPoints[5]; break;
        case 6: res = controlPoints[6]; break;
        case 7: res = controlPoints[7]; break;
        case 8: res = controlPoints[8]; break;
        case 9: res = controlPoints[9]; break;
        case 10: res = controlPoints[10]; break;
        case 11: res = controlPoints[11]; break;
        case 12: res = controlPoints[12]; break;
        case 13: res = controlPoints[13]; break;
        case 14: res = controlPoints[14]; break;
        case 15: res = controlPoints[15]; break;
        case 16: res = controlPoints[16]; break;
        case 17: res = controlPoints[17]; break;
        case 18: res = controlPoints[18]; break;
        case 19: res = controlPoints[19]; break;
        case 20: res = controlPoints[20]; break;
        case 21: res = controlPoints[21]; break;
        case 22: res = controlPoints[22]; break;
        case 23: res = controlPoints[23]; break;
        case 24: res = controlPoints[24]; break;
        case 25: res = controlPoints[25]; break;
        case 26: res = controlPoints[26]; break;
        case 27: res = controlPoints[27]; break;
        case 28: res = controlPoints[28]; break;
        case 29: res = controlPoints[29]; break;
        case 30: res = controlPoints[30]; break;
        case 31: res = controlPoints[31]; break;
        case 32: res = controlPoints[32]; break;
        case 33: res = controlPoints[33]; break;
        case 34: res = controlPoints[34]; break;
        case 35: res = controlPoints[35]; break;
        case 36: res = controlPoints[36]; break;
        case 37: res = controlPoints[37]; break;
        case 38: res = controlPoints[38]; break;
        case 39: res = controlPoints[39]; break;
        case 40: res = controlPoints[40]; break;
        case 41: res = controlPoints[41]; break;
        case 42: res = controlPoints[42]; break;
        case 43: res = controlPoints[43]; break;
        case 44: res = controlPoints[44]; break;
        case 45: res = controlPoints[45]; break;
        case 46: res = controlPoints[46]; break;
        case 47: res = controlPoints[47]; break;
        case 48: res = controlPoints[48]; break;
        case 49: res = controlPoints[49]; break;
        case 50: res = controlPoints[50]; break;
        case 51: res = controlPoints[51]; break;
        case 52: res = controlPoints[52]; break;
        case 53: res = controlPoints[53]; break;
        case 54: res = controlPoints[54]; break;
        case 55: res = controlPoints[55]; break;
        case 56: res = controlPoints[56]; break;
        case 57: res = controlPoints[57]; break;
        case 58: res = controlPoints[58]; break;
        case 59: res = controlPoints[59]; break;
        case 60: res = controlPoints[60]; break;
        case 61: res = controlPoints[61]; break;
        case 62: res = controlPoints[62]; break;
        case 63: res = controlPoints[63]; break;
        case 64: res = controlPoints[64]; break;
        case 65: res = controlPoints[65]; break;
        case 66: res = controlPoints[66]; break;
        case 67: res = controlPoints[67]; break;
        case 68: res = controlPoints[68]; break;
        case 69: res = controlPoints[69]; break;
        case 70: res = controlPoints[70]; break;
        case 71: res = controlPoints[71]; break;
        case 72: res = controlPoints[72]; break;
        case 73: res = controlPoints[73]; break;
        case 74: res = controlPoints[74]; break;
        // default: res is already vec2(0.0) if no case matches
    }
    return res;
}

float vec2ToFloat(vec2 val){
    float res = val.x + val.y/255.0;
    return res;
}
vec2 floatToVec2(float val){
    float a = floor(val*255.0)/255.0;
    float b = fract(val*255.0);
    return vec2(a, b);
}

float vec4ToFloat(vec4 val){
    float res = val.x * 255.0 + val.y + val.z/255.0;
    res = val.z < 0.5 ? res : -res;
    return res;
}
vec4 floatToVec4(float val){
    float d = val < 0.?1.:0.;
    float a = floor(abs(val))/255.0;
    float b = floor(fract(abs(val))*255.0)/255.0;
    float c = fract(fract(abs(val))*255.0);
    return vec4(a, b, c, d);
}

float Linear(float x1, float y1, float x2, float y2, float x)
{
    if (x2 <= x1)
    {
        if (x > x2)
        {
            return y2;
        }
        else
        {
            return y1;
        }
    }
    return (x-x1)*(y2-y1)/(x2-x1) + y1;
}

float Bezier(float p0, float p1, float p2, float p3, float t)
{
    float result;
    float p0p1 = (1.0 - t) * p0 + t * p1;
    float p1p2 = (1.0 - t) * p1 + t * p2;
    float p2p3 = (1.0 - t) * p2 + t * p3;
    float p0p1p2 = (1.0 - t) * p0p1 + t * p1p2;
    float p1p2p3 = (1.0 - t) * p1p2 + t * p2p3;
    result = (1.0 - t) * p0p1p2 + t * p1p2p3;
    return result;
}

const float ESP = 0.00005;
float computeT2(float p0, float p1, float p2, float p3, float p) 
{
    if (abs(p0 - p) < ESP)
    {
        return 0.0;
    }    
    if (abs(p3 - p) < ESP)
    {
        return 1.0;
    }
    float startT = 0.0;
    float endT = 1.0;
    float halfT = 0.5;

    float halfP = Bezier(p0, p1, p2, p3, halfT);

    for (int i =0; i < 20;i++)
    {
        if (abs(halfP - p) < ESP)
        {
            break;
        }
        if(halfP < p){
            startT = halfT;
        }else {
            endT = halfT;
        }
        halfT = (startT + endT)/2.0;
        halfP = Bezier(p0, p1, p2, p3, halfT);
    }
    return halfT;
}

float genBezierY(float x)
{
    int nums = 0;
    for (int j = 0; j < 75; j++)
    {
        nums = j;
        if (j >= pointsNums)
        {
            break;
        }
    }
    if(x < getControlPoints(0).x)
    {
        return Linear(getControlPoints(0).x, getControlPoints(0).y, getControlPoints(1).x, getControlPoints(1).y, x);
    }
    else if(x > getControlPoints((nums-1) * 3).x)
    {
        return Linear(getControlPoints((nums-1) * 3 - 1).x, getControlPoints((nums-1) * 3 - 1).y, getControlPoints((nums-1) * 3).x, getControlPoints((nums-1) * 3).y, x);
    }

    int i = 0;
    for (int j = 0; j < 75; j++)
    {
        i = j;
        if (j >= pointsNums)
        {
            break;
        }
        if (x < getControlPoints(j*3).x)
        {
            break;
        }
    }
    vec2 p0 = getControlPoints((i-1)*3);
    vec2 p1 = getControlPoints((i-1)*3 + 1);
    vec2 p2 = getControlPoints((i-1)*3 + 2);
    vec2 p3 = getControlPoints(i*3);
    float t = computeT2(p0.x, p1.x, p2.x, p3.x, x);
    float y = Bezier(p0.y, p1.y, p2.y, p3.y, t);
    return y;
}

void main(void) {
    float y = genBezierY(uv0.x);
    outColor = floatToVec4(y);
    // outColor = vec4(floatToVec2(y), 1.0, 1.0);
    // outColor = vec4(0, uv0.x, 0, 0.0);
}
