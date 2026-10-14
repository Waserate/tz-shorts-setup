import {AbsoluteFill, Composition, interpolate, useCurrentFrame} from 'remotion';

// Blank 9:16 Shorts canvas. Ask Claude to build on this (titles, captions, intros).
const Short: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 15], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{backgroundColor: '#111', justifyContent: 'center', alignItems: 'center'}}>
      <div style={{color: 'white', fontSize: 96, fontWeight: 700, opacity}}>Take A Zeat</div>
    </AbsoluteFill>
  );
};

export const RemotionRoot: React.FC = () => (
  <Composition id="Short" component={Short} durationInFrames={90} fps={30} width={1080} height={1920} />
);
