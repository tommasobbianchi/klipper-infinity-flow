import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
  AbsoluteFill,
} from "remotion";
import { COLORS, FONT } from "../theme";

export const SceneHook = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Background particles / grid fade in
  const bgOpacity = interpolate(frame, [0, fps * 1], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Tag line slides up + fades in
  const tagTranslate = interpolate(frame, [0, fps * 0.8], [40, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });
  const tagOpacity = interpolate(frame, [0, fps * 0.8], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Main headline — spring scale entrance
  const headlineScale = spring({
    frame: frame - Math.round(fps * 0.4),
    fps,
    config: { damping: 200 },
    durationInFrames: fps * 1.2,
  });

  // Sub-headline fades in after headline
  const subOpacity = interpolate(
    frame,
    [fps * 1.2, fps * 2.0],
    [0, 1],
    { extrapolateRight: "clamp" }
  );
  const subTranslate = interpolate(
    frame,
    [fps * 1.2, fps * 2.0],
    [20, 0],
    { extrapolateRight: "clamp", easing: Easing.out(Easing.quad) }
  );

  // Glowing accent line width
  const lineWidth = interpolate(frame, [fps * 1.8, fps * 3.0], [0, 320], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  // Glow pulse (subtle)
  const glow = interpolate(
    Math.sin((frame / fps) * Math.PI * 2),
    [-1, 1],
    [0.6, 1.0]
  );

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 40%, #0f1f2e 0%, ${COLORS.bg} 70%)`,
        fontFamily: FONT.sans,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "0 80px",
      }}
    >
      {/* Subtle grid background */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: bgOpacity * 0.12,
          backgroundImage: `
            linear-gradient(${COLORS.accentDim} 1px, transparent 1px),
            linear-gradient(90deg, ${COLORS.accentDim} 1px, transparent 1px)
          `,
          backgroundSize: "80px 80px",
        }}
      />

      {/* Brand tag */}
      <div
        style={{
          position: "absolute",
          top: 120,
          opacity: tagOpacity,
          transform: `translateY(${tagTranslate}px)`,
          display: "flex",
          alignItems: "center",
          gap: 14,
        }}
      >
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: COLORS.accent,
            boxShadow: `0 0 16px ${COLORS.accent}`,
            opacity: glow,
          }}
        />
        <span
          style={{
            fontFamily: FONT.mono,
            fontSize: 28,
            color: COLORS.accent,
            letterSpacing: "0.15em",
            textTransform: "uppercase",
          }}
        >
          native research
        </span>
      </div>

      {/* Main headline */}
      <div
        style={{
          transform: `scale(${headlineScale})`,
          textAlign: "center",
          lineHeight: 1.1,
        }}
      >
        <div
          style={{
            fontSize: 108,
            fontWeight: 900,
            color: COLORS.textPrimary,
            letterSpacing: "-0.02em",
          }}
        >
          Infinity
        </div>
        <div
          style={{
            fontSize: 108,
            fontWeight: 900,
            color: COLORS.accent,
            letterSpacing: "-0.02em",
            textShadow: `0 0 60px ${COLORS.accent}88`,
          }}
        >
          Flow S1+
        </div>
        <div
          style={{
            fontSize: 76,
            fontWeight: 700,
            color: COLORS.textPrimary,
            letterSpacing: "-0.01em",
          }}
        >
          meets Klipper
        </div>
      </div>

      {/* Accent line */}
      <div
        style={{
          marginTop: 48,
          height: 3,
          width: lineWidth,
          background: `linear-gradient(90deg, transparent, ${COLORS.accent}, transparent)`,
          borderRadius: 2,
          boxShadow: `0 0 20px ${COLORS.accent}`,
        }}
      />

      {/* Sub headline */}
      <div
        style={{
          marginTop: 48,
          opacity: subOpacity,
          transform: `translateY(${subTranslate}px)`,
          textAlign: "center",
          fontSize: 44,
          color: COLORS.textSecondary,
          fontWeight: 400,
          lineHeight: 1.4,
        }}
      >
        Open source integration.
        <br />
        Zero hardware mods required.
      </div>
    </AbsoluteFill>
  );
};
