import { Composition } from "remotion";
import { InfinityFlowVideo } from "./InfinityFlowVideo";

// 9:16 vertical format for YouTube Shorts / Reels / TikTok
// 30fps × 43 seconds = 1290 frames (added KlipperScreen scene)
const FPS = 30;
const DURATION_S = 43;

export const Root = () => {
  return (
    <Composition
      id="InfinityFlowVideo"
      component={InfinityFlowVideo}
      durationInFrames={FPS * DURATION_S}
      fps={FPS}
      width={1080}
      height={1920}
    />
  );
};
