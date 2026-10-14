import {Config} from '@remotion/cli/config';

// Render Chrome on the GPU (ANGLE/D3D). On the original PC this was ~3x faster than the default.
Config.setChromiumOpenGlRenderer('angle');
