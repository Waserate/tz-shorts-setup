#pragma clang diagnostic ignored "-Wmissing-prototypes"

#include <metal_stdlib>
#include <simd/simd.h>

using namespace metal;

struct buffer_t
{
    float u_radiusY;
    float u_sigmaY;
    float u_dy;
    float u_threshold;
    float u_intensity;
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

fragment main0_out main0(main0_in in [[stage_in]], constant buffer_t& buffer, texture2d<float> u_inputTexture [[texture(0)]], texture2d<float> u_albedo [[texture(1)]], texture2d<float> mask123 [[texture(2)]], sampler u_inputTextureSmplr [[sampler(0)]], sampler u_albedoSmplr [[sampler(1)]], sampler mask123Smplr [[sampler(2)]])
{
    main0_out out = {};
    float4 _t2 = u_inputTexture.sample(u_inputTextureSmplr, in.uv0);
    if (buffer.u_radiusY < 0.001000000047497451305389404296875)
    {
        out.o_fragColor = _t2;
        return out;
    }
    float _t4 = 0.0;
    float4 _t5 = float4(0.0);
    float _65 = -buffer.u_radiusY;
    for (float _t6 = _65; _t6 <= buffer.u_radiusY; _t6 += buffer.u_dy)
    {
        float2 _79 = in.uv0 + float2(0.0, _t6);
        float2 _t7 = _79;
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
            float param_1 = buffer.u_sigmaY;
            float _100 = _f0(param, param_1);
            _t4 += _100;
            _t5 += (u_albedo.sample(u_albedoSmplr, _79) * _100);
        }
    }
    float4 _120 = _t2;
    float4 _122 = _120 - (_t5 / float4(_t4));
    float3 _142 = smoothstep(float4(buffer.u_threshold / 5.0), float4(buffer.u_threshold), abs(_122)).xyz;
    float3 _145 = _122.xyz;
    float3 _147 = _120.xyz + ((_142 * buffer.u_intensity) * _145);
    _t2.x = _147.x;
    _t2.y = _147.y;
    _t2.z = _147.z;
    float4 _t12 = mask123.sample(mask123Smplr, in.uv0);
    float4 _162 = _t2;
    float4 _t13 = _162;
    float3 _172 = _162.xyz + ((_142 * 0.20000000298023223876953125) * _145);
    _t13.x = _172.x;
    _t13.y = _172.y;
    _t13.z = _172.z;
    float4 _184 = mix(_162, _t13, float4(_t12.y));
    _t2 = _184;
    out.o_fragColor = fast::clamp(_184, float4(0.0), float4(1.0));
    return out;
}

