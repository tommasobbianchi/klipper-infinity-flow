import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  createTikTokStyleCaptions,
  type Caption,
  type TikTokPage,
} from "@remotion/captions";
import captionsData from "./captions.json";
import { FONT } from "./theme";

const CAPTIONS: Caption[] = captionsData as Caption[];
const SWITCH_EVERY_MS = 1800;

const CaptionPage: React.FC<{ page: TikTokPage }> = ({ page }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentMs = page.startMs + (frame / fps) * 1000;

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: 120,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          fontFamily: FONT.sans,
          fontSize: 52,
          fontWeight: 800,
          textAlign: "center",
          lineHeight: 1.25,
          maxWidth: 900,
          padding: "14px 32px",
          borderRadius: 20,
          background: "rgba(0,0,0,0.55)",
        }}
      >
        {page.tokens.map((token) => {
          const isActive =
            token.fromMs <= currentMs && token.toMs > currentMs;
          return (
            <span
              key={token.fromMs}
              style={{
                color: isActive ? "#22d3ee" : "#f9fafb",
                textShadow: isActive
                  ? "0 0 20px rgba(34,211,238,0.6)"
                  : "0 2px 8px rgba(0,0,0,0.8)",
                transition: "color 0.05s",
              }}
            >
              {token.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

export const Captions: React.FC = () => {
  const { fps } = useVideoConfig();

  const { pages } = useMemo(
    () =>
      createTikTokStyleCaptions({
        captions: CAPTIONS,
        combineTokensWithinMilliseconds: SWITCH_EVERY_MS,
      }),
    []
  );

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {pages.map((page, i) => {
        const nextPage = pages[i + 1] ?? null;
        const startFrame = Math.round((page.startMs / 1000) * fps);
        const endFrame = Math.round(
          Math.min(
            nextPage ? (nextPage.startMs / 1000) * fps : Infinity,
            startFrame + (SWITCH_EVERY_MS / 1000) * fps
          )
        );
        const durationInFrames = endFrame - startFrame;
        if (durationInFrames <= 0) return null;

        return (
          <Sequence key={i} from={startFrame} durationInFrames={durationInFrames}>
            <CaptionPage page={page} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
