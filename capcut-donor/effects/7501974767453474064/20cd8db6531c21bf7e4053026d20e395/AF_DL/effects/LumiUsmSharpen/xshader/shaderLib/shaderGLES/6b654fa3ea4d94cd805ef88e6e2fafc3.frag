precision highp float;
precision highp int;

uniform mediump sampler2D u_inputTexture;
uniform mediump sampler2D u_albedo;
uniform float u_radiusY;
uniform float u_sigmaY;
uniform float u_dy;
uniform float u_threshold;
uniform float u_intensity;
uniform mediump sampler2D mask123;

varying vec2 uv0;

float _f0(float _p0, float _p1)
{
    return exp((((-0.5) * _p0) * _p0) / (_p1 * _p1));
}

void main()
{
    vec4 _t2 = texture2D(u_inputTexture, uv0);
    if (u_radiusY < 0.001000000047497451305389404296875)
    {
        gl_FragData[0] = _t2;
        return;
    }
    float _t4 = 0.0;
    vec4 _t5 = vec4(0.0);
    float _65 = -u_radiusY;
    //for (float _t6 = _65; _t6 <= u_radiusY; _t6 += u_dy)
    float _t6 = _65;
    for (int i=0; i<30; i++)
    {
        if (_t6 > u_radiusY)
        {
            break;
        }
        vec2 _79 = uv0 + vec2(0.0, _t6);
        vec2 _t7 = _79;
        bool _84 = _t7.y >= 0.0;
        bool _91;
        if (_84)
        {
            _91 = _t7.y <= 1.0;
        }
        else
        {
            _91 = _84;
        }
        if (_91)
        {
            float param = _t6;
            float param_1 = u_sigmaY;
            float _100 = _f0(param, param_1);
            _t4 += _100;
            _t5 += (texture2D(u_albedo, _79) * _100);
        }
        _t6 += u_dy;
    }
    vec4 _120 = _t2;
    vec4 _122 = _120 - (_t5 / vec4(_t4));
    vec3 _142 = smoothstep(vec4(u_threshold / 5.0), vec4(u_threshold), abs(_122)).xyz;
    vec3 _145 = _122.xyz;
    vec3 _147 = _120.xyz + ((_142 * u_intensity) * _145);
    _t2.x = _147.x;
    _t2.y = _147.y;
    _t2.z = _147.z;
    vec4 _t12 = texture2D(mask123, uv0);
    vec4 _162 = _t2;
    vec4 _t13 = _162;
    vec3 _172 = _162.xyz + ((_142 * 0.20000000298023223876953125) * _145);
    _t13.x = _172.x;
    _t13.y = _172.y;
    _t13.z = _172.z;
    vec4 _184 = mix(_162, _t13, vec4(_t12.y));
    _t2 = _184;
    gl_FragData[0] = clamp(_184, vec4(0.0), vec4(1.0));
}

