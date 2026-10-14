#pragma clang diagnostic ignored "-Wmissing-prototypes"

#include <metal_stdlib>
#include <simd/simd.h>

using namespace metal;

struct buffer_t
{
    float u_radiusX;
    float u_sigmaX;
    float u_dx;
};

struct main0_out
{
    float4 o_fragColor [[color(0)]];
};

struct main0_in
{
    float2 uv0 [[user(locn0)]];
};

static inline __attribute__((always_inline))
float _f0(thread const float& _p0, thread const float& _p1)
{
    return exp((((-0.5) * _p0) * _p0) / (_p1 * _p1));
}

fragment main0_out main0(main0_in in [[stage_in]], constant buffer_t& buffer, texture2d<float> u_inputTexture [[texture(0)]], sampler u_inputTextureSmplr [[sampler(0)]])
{
    main0_out out = {};
    float4 _t2 = u_inputTexture.sample(u_inputTextureSmplr, in.uv0);
    if (buffer.u_radiusX < 0.001000000047497451305389404296875)
    {
        out.o_fragColor = _t2;
        return out;
    }
    float _t3 = 0.0;
    float4 _t4 = float4(0.0);
    float _60 = -buffer.u_radiusX;
    for (float _t5 = _60; _t5 <= buffer.u_radiusX; _t5 += buffer.u_dx)
    {
        float2 _74 = in.uv0 + float2(_t5, 0.0);
        float2 _t6 = _74;
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
            float param_1 = buffer.u_sigmaX;
            float _95 = _f0(param, param_1);
            _t3 += _95;
            _t4 += (u_inputTexture.sample(u_inputTextureSmplr, _74) * _95);
        }
    }
    float4 _113 = _t4 / float4(_t3);
    _t2 = _113;
    out.o_fragColor = fast::clamp(_113, float4(0.0), float4(1.0));
    return out;
}

