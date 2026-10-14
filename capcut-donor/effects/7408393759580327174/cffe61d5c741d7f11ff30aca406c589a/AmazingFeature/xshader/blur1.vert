precision highp float;

attribute vec3 position;
attribute vec2 texcoord0;

uniform float texBlurWidthOffset;
uniform float texBlurHeightOffset;

varying vec2 textureCoordinate;
varying vec4 textureShift_1;
varying vec4 textureShift_2;
varying vec4 textureShift_3;
varying vec4 textureShift_4;

void main()
{
    gl_Position = vec4(position, 1.0);
    textureCoordinate = texcoord0;
    
    vec2 singleStepOffset = vec2(texBlurWidthOffset * 2.5, texBlurHeightOffset * 2.5);

	textureShift_1 = vec4(textureCoordinate.xy - singleStepOffset, textureCoordinate.xy + singleStepOffset);
	textureShift_2 = vec4(textureCoordinate.xy - 2.0 * singleStepOffset, textureCoordinate.xy + 2.0 * singleStepOffset);
	textureShift_3 = vec4(textureCoordinate.xy - 3.0 * singleStepOffset, textureCoordinate.xy + 3.0 * singleStepOffset);
	textureShift_4 = vec4(textureCoordinate.xy - 4.0 * singleStepOffset, textureCoordinate.xy + 4.0 * singleStepOffset);
}