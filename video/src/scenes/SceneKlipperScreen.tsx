import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
  AbsoluteFill,
  Img,
  staticFile,
} from "remotion";
import { COLORS, FONT } from "../theme";

export const SceneKlipperScreen = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, fps * 0.6], [0, 1], {
    extrapolateRight: "clamp",
  });
  const titleY = interpolate(frame, [0, fps * 0.6], [20, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  // Screenshot scales in from 0.85 to 1
  const imgScale = spring({
    frame: frame - fps * 0.4,
    fps,
    config: { damping: 18, stiffness: 160 },
  });
  const imgOpacity = interpolate(frame, [fps * 0.3, fps * 0.9], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
  });

  // Subtle badge fades in after image
  const badgeOpacity = interpolate(frame, [fps * 1.4, fps * 2.0], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 20%, #091822 0%, ${COLORS.bg} 65%)`,
        fontFamily: FONT.sans,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-start",
        padding: "100px 60px 60px",
      }}
    >
      {/* Title */}
      <div
        style={{
          opacity: titleOpacity,
          transform: `translateY(${titleY}px)`,
          textAlign: "center",
          marginBottom: 48,
        }}
      >
        <div
          style={{
            fontFamily: FONT.mono,
            fontSize: 28,
            color: COLORS.accent,
            letterSpacing: "0.2em",
            textTransform: "uppercase",
            marginBottom: 12,
          }}
        >
          KlipperScreen widget
        </div>
        <div
          style={{
            fontSize: 60,
            fontWeight: 800,
            color: COLORS.textPrimary,
            lineHeight: 1.1,
          }}
        >
          Slot status,
          <br />
          one tap away
        </div>
      </div>

      {/* Screenshot */}
      <div
        style={{
          opacity: imgOpacity,
          transform: `scale(${Math.min(imgScale, 1) * 0.85 + 0.15})`,
          borderRadius: 20,
          overflow: "hidden",
          boxShadow: `0 0 60px ${COLORS.accent}20, 0 20px 80px #00000080`,
          border: `1.5px solid ${COLORS.bgCardBorder}`,
          width: "100%",
          maxWidth: 860,
        }}
      >
        <Img
          src={staticFile("ks_if_final.png")}
          style={{ width: "100%", display: "block" }}
        />
      </div>

      {/* "Live on printer" badge */}
      <div
        style={{
          opacity: badgeOpacity,
          marginTop: 36,
          background: `${COLORS.green}18`,
          border: `1.5px solid ${COLORS.green}50`,
          borderRadius: 100,
          padding: "14px 44px",
          display: "flex",
          alignItems: "center",
          gap: 16,
        }}
      >
        <div
          style={{
            width: 12,
            height: 12,
            borderRadius: "50%",
            background: COLORS.green,
            boxShadow: `0 0 10px ${COLORS.green}`,
          }}
        />
        <span
          style={{
            fontFamily: FONT.mono,
            fontSize: 28,
            color: COLORS.green,
            fontWeight: 600,
          }}
        >
          Live on IdeaFormer IR3 V2
        </span>
      </div>
    </AbsoluteFill>
  );
};
