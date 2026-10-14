attribute vec3 attPosition;
attribute vec2 attUV;
varying highp vec2 textureCoordinate[9];
uniform highp vec2 imagestep;

void main()
{
    gl_Position = vec4(attPosition, 1.0);
    textureCoordinate[4] = attUV;
    textureCoordinate[0] = textureCoordinate[4] + imagestep * vec2(-1.5, -1.5);
    textureCoordinate[1] = textureCoordinate[4] + imagestep * vec2(0.0, -1.5);
    textureCoordinate[2] = textureCoordinate[4] + imagestep * vec2(1.5, -1.5);
    textureCoordinate[3] = textureCoordinate[4] + imagestep * vec2(-1.5, 0.0);
    textureCoordinate[5] = textureCoordinate[4] + imagestep * vec2(1.5, 0.0);
    textureCoordinate[6] = textureCoordinate[4] + imagestep * vec2(-1.5, 1.5);
    textureCoordinate[7] = textureCoordinate[4] + imagestep * vec2(0.0, 1.5);
    textureCoordinate[8] = textureCoordinate[4] + imagestep * vec2(1.5, 1.5);
}
