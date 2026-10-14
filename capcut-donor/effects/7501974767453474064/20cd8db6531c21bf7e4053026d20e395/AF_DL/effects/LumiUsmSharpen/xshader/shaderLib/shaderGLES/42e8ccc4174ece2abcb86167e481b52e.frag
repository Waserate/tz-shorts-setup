precision highp float;
precision highp int;

uniform mediump sampler2D u_inputTexture;
uniform float u_radiusX;
uniform float u_sigmaX;
uniform float u_dx;

varying vec2 uv0;

float _f0(float _p0, float _p1)
{
    return exp((((-0.5) * _p0) * _p0) / (_p1 * _p1));
}

void main()
{
    vec4 _t2 = texture2D(u_inputTexture, uv0);
    if (u_radiusX < 0.001000000047497451305389404296875)
    {
        gl_FragData[0] = _t2;
        return;
    }
    float _t3 = 0.0;
    vec4 _t4 = vec4(0.0);
    float _60 = -u_radiusX;
    //for (float _t5 = _60; _t5 <= u_radiusX; _t5 += u_dx)
    float _t5 = _60;
    for (int i=0; i<30; i++)
    {
        if (_t5 > u_radiusX)
        {
            break;
        }
        vec2 _74 = uv0 + vec2(_t5, 0.0);
        vec2 _t6 = _74;
        bool _79 = _t6.x >= 0.0;
        bool _86;
        if (_79)
        {
            _86 = _t6.x <= 1.0;
        }
        else
        {
            _86 = _79;
        }
        if (_86)
        {
            float param = _t5;
            float param_1 = u_sigmaX;
            float _95 = _f0(param, param_1);
            _t3 += _95;
            _t4 += (texture2D(u_inputTexture, _74) * _95);
        }
        _t5 += u_dx;
    }
    vec4 _113 = _t4 / vec4(_t3);
    _t2 = _113;
    gl_FragData[0] = clamp(_113, vec4(0.0), vec4(1.0));
}

