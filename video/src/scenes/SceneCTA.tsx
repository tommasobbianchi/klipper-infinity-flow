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

export const SceneCTA = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Background glow
  const glowOpacity = interpolate(frame, [0, fps * 1], [0, 1], {
    extrapolateRight: "clamp",
  });

  // "Open source" badge scales in
  const badgeScale = spring({
    frame: frame - fps * 0.3,
    fps,
    config: { damping: 12, stiffness: 160 },
  });

  // Headline appears
  const headlineOpacity = interpolate(frame, [fps * 0.6, fps * 1.4], [0, 1], {
    extrapolateRight: "clamp",
  });
  const headlineY = interpolate(frame, [fps * 0.6, fps * 1.4], [30, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  // GitHub link slides up
  const githubOpacity = interpolate(frame, [fps * 1.4, fps * 2.2], [0, 1], {
    extrapolateRight: "clamp",
  });
  const githubY = interpolate(frame, [fps * 1.4, fps * 2.2], [24, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  // Feature list items
  const features = [
    { icon: "🔌", text: "Virtual filament sensors" },
    { icon: "⏸️", text: "Auto-pause on runout" },
    { icon: "🔄", text: "Smart swap detection" },
    { icon: "📱", text: "KlipperScreen widget" },
  ];

  // Brand tag at bottom
  const brandOpacity = interpolate(frame, [fps * 4, fps * 5], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Subtle pulsing glow on accent circle
  const pulse = interpolate(
    Math.sin((frame / fps) * Math.PI * 1.5),
    [-1, 1],
    [0.7, 1.0]
  );

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 50%, #0a1628 0%, ${COLORS.bg} 70%)`,
        fontFamily: FONT.sans,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "80px 70px",
      }}
    >
      {/* Glowing circle background */}
      <div
        style={{
          position: "absolute",
          top: "35%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: 600,
          height: 600,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${COLORS.accent}12 0%, transparent 70%)`,
          opacity: glowOpacity * pulse,
        }}
      />

      {/* Open source badge */}
      <div
        style={{
          transform: `scale(${badgeScale})`,
          background: `${COLORS.accent}18`,
          border: `1.5px solid ${COLORS.accent}50`,
          borderRadius: 100,
          padding: "14px 40px",
          display: "flex",
          alignItems: "center",
          gap: 14,
          marginBottom: 44,
        }}
      >
        <div style={{ fontSize: 28 }}>⭐</div>
        <span
          style={{
            fontFamily: FONT.mono,
            fontSize: 28,
            color: COLORS.accent,
            fontWeight: 600,
          }}
        >
          Open source · Free forever
        </span>
      </div>

      {/* Main CTA */}
      <div
        style={{
          opacity: headlineOpacity,
          transform: `translateY(${headlineY}px)`,
          textAlign: "center",
          marginBottom: 56,
        }}
      >
        <div
          style={{
            fontSize: 72,
            fontWeight: 900,
            color: COLORS.textPrimary,
            lineHeight: 1.1,
          }}
        >
          Start today.
        </div>
        <div
          style={{
            fontSize: 46,
            fontWeight: 400,
            color: COLORS.textSecondary,
            marginTop: 12,
          }}
        >
          Your printer. Your filament.
          <br />
          Fully automated.
        </div>
      </div>

      {/* GitHub card */}
      <div
        style={{
          opacity: githubOpacity,
          transform: `translateY(${githubY}px)`,
          background: COLORS.bgCard,
          border: `1.5px solid ${COLORS.bgCardBorder}`,
          borderRadius: 24,
          padding: "32px 48px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 12,
          width: "100%",
          marginBottom: 48,
        }}
      >
        <div style={{ fontSize: 42 }}>🐙</div>
        <div
          style={{
            fontFamily: FONT.mono,
            fontSize: 30,
            color: COLORS.accent,
            fontWeight: 600,
            wordBreak: "break-all",
            textAlign: "center",
          }}
        >
          github.com/
          <br />
          native-research/
          <br />
          klipper-infinity-flow
        </div>
      </div>

      {/* Feature chips */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          justifyContent: "center",
          marginBottom: 60,
        }}
      >
        {features.map((f, i) => {
          const chipOpacity = interpolate(
            frame,
            [fps * (2.4 + i * 0.3), fps * (2.8 + i * 0.3)],
            [0, 1],
            { extrapolateRight: "clamp", extrapolateLeft: "clamp" }
          );
          const chipScale = spring({
            frame: frame - fps * (2.4 + i * 0.3),
            fps,
            config: { damping: 14, stiffness: 200 },
          });
          return (
            <div
              key={f.text}
              style={{
                opacity: chipOpacity,
                transform: `scale(${chipScale})`,
                background: `${COLORS.bgCard}`,
                border: `1px solid ${COLORS.bgCardBorder}`,
                borderRadius: 100,
                padding: "12px 28px",
                display: "flex",
                alignItems: "center",
                gap: 10,
                fontFamily: FONT.sans,
                fontSize: 26,
                color: COLORS.textSecondary,
              }}
            >
              <span style={{ fontSize: 24 }}>{f.icon}</span>
              {f.text}
            </div>
          );
        })}
      </div>

      {/* Brand watermark */}
      <div
        style={{
          position: "absolute",
          bottom: 80,
          opacity: brandOpacity,
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: COLORS.accent,
            boxShadow: `0 0 12px ${COLORS.accent}`,
          }}
        />
        <span
          style={{
            fontFamily: FONT.mono,
            fontSize: 26,
            color: COLORS.textMuted,
            letterSpacing: "0.15em",
            textTransform: "uppercase",
          }}
        >
          native research
        </span>
      </div>
    </AbsoluteFill>
  );
};
