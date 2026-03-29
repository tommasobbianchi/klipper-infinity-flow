import React from "react";
import { AbsoluteFill, Audio, staticFile, useVideoConfig } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { SceneHook } from "./scenes/SceneHook";
import { SceneArchitecture } from "./scenes/SceneArchitecture";
import { SceneSensors } from "./scenes/SceneSensors";
import { SceneInstall } from "./scenes/SceneInstall";
import { SceneCTA } from "./scenes/SceneCTA";
import { SceneKlipperScreen } from "./scenes/SceneKlipperScreen";
import { Captions } from "./Captions";

// Scene durations in frames (30fps)
// Hook:            0–4s  = 120f
// Architecture:    4–14s = 300f
// Sensors:        14–22s = 240f
// KlipperScreen:  22–28s = 180f
// Install:        28–36s = 240f
// CTA:            36–43s = 210f
// Transitions overlap by 15 frames each

const TRANSITION = linearTiming({ durationInFrames: 15 });

export const InfinityFlowVideo = () => {
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill>
      {/* Narration audio */}
      <Audio src={staticFile("narration.mp3")} />

      {/* Scene transitions */}
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={4 * fps + 15}>
          <SceneHook />
        </TransitionSeries.Sequence>

        <TransitionSeries.Transition presentation={fade()} timing={TRANSITION} />

        <TransitionSeries.Sequence durationInFrames={10 * fps + 15}>
          <SceneArchitecture />
        </TransitionSeries.Sequence>

        <TransitionSeries.Transition presentation={fade()} timing={TRANSITION} />

        <TransitionSeries.Sequence durationInFrames={8 * fps + 15}>
          <SceneSensors />
        </TransitionSeries.Sequence>

        <TransitionSeries.Transition presentation={fade()} timing={TRANSITION} />

        <TransitionSeries.Sequence durationInFrames={6 * fps + 15}>
          <SceneKlipperScreen />
        </TransitionSeries.Sequence>

        <TransitionSeries.Transition presentation={fade()} timing={TRANSITION} />

        <TransitionSeries.Sequence durationInFrames={8 * fps + 15}>
          <SceneInstall />
        </TransitionSeries.Sequence>

        <TransitionSeries.Transition presentation={fade()} timing={TRANSITION} />

        <TransitionSeries.Sequence durationInFrames={7 * fps}>
          <SceneCTA />
        </TransitionSeries.Sequence>
      </TransitionSeries>

      {/* Captions overlay — renders on top of all scenes */}
      <Captions />
    </AbsoluteFill>
  );
};
