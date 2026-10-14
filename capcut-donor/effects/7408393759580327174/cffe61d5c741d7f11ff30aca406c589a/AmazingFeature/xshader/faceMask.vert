 attribute vec3 attPosition;
 attribute vec2 attUV;
 varying vec2 sucaiTexCoord;
 varying vec2 srcUV;

 uniform mat4 uMVPMatrix;
 uniform mat4 uSTMatrix;

 void main(void){
     gl_Position = uMVPMatrix * vec4(attPosition.xy, 0.0, 1.0);
     vec4 coord = uSTMatrix * vec4(attUV.xy, 0.0, 1.0);
     sucaiTexCoord = vec2(coord.x, 1.0 - coord.y);
     srcUV = vec2(coord.x, coord.y);
 }
 