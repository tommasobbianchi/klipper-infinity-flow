import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
  AbsoluteFill,
  Sequence,
} from "remotion";
import { COLORS, FONT } from "../theme";

// Each node in the architecture pipeline
type NodeProps = {
  icon: string;
  label: string;
  sublabel?: string;
  color?: string;
  frame: number;
  fps: number;
  delay: number;
};

const ArchNode: React.FC<NodeProps> = ({
  icon,
  label,
  sublabel,
  color,
  frame,
  fps,
  delay,
}) => {
  const localFrame = frame - delay;
  const sc = spring({
    frame: localFrame,
    fps,
    config: { damping: 14, stiffness: 180 },
    durationInFrames: fps,
  });
  const opacity = interpolate(localFrame, [0, 8], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
  });

  const nodeColor = color || COLORS.accent;

  return (
    <div
      style={{
        transform: `scale(${sc})`,
        opacity,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 12,
      }}
    >
      {/* Icon circle */}
      <div
        style={{
          width: 120,
          height: 120,
          borderRadius: "50%",
          background: `${nodeColor}18`,
          border: `2px solid ${nodeColor}60`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 52,
          boxShadow: `0 0 30px ${nodeColor}30`,
        }}
      >
        {icon}
      </div>
      {/* Label */}
      <div
        style={{
          fontFamily: FONT.sans,
          fontWeight: 700,
          fontSize: 30,
          color: COLORS.textPrimary,
          textAlign: "center",
        }}
      >
        {label}
      </div>
      {sublabel && (
        <div
          style={{
            fontFamily: FONT.mono,
            fontSize: 22,
            color: nodeColor,
            textAlign: "center",
          }}
        >
          {sublabel}
        </div>
      )}
    </div>
  );
};

// Animated arrow between nodes
type ArrowProps = {
  frame: number;
  fps: number;
  delay: number;
  label?: string;
};

const FlowArrow: React.FC<ArrowProps> = ({ frame, fps, delay, label }) => {
  const localFrame = frame - delay;
  const progress = interpolate(localFrame, [0, fps * 0.8], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
    easing: Easing.out(Easing.quad),
  });

  // Arrow travels along a line — we animate a moving dot
  const dotX = interpolate(progress, [0, 1], [0, 100]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 6,
      }}
    >
      {/* Line + animated dot */}
      <div
        style={{
          position: "relative",
          width: 3,
          height: 80,
          background: `${COLORS.accentDim}50`,
        }}
      >
        {/* Traveling glow */}
        <div
          style={{
            position: "absolute",
            top: `${interpolate(progress, [0, 1], [0, 72])}px`,
            left: "50%",
            transform: "translateX(-50%)",
            width: 10,
            height: 10,
            borderRadius: "50%",
            background: COLORS.accent,
            boxShadow: `0 0 14px ${COLORS.accent}`,
            opacity: progress > 0 ? 1 : 0,
          }}
        />
      </div>
      {/* Arrowhead */}
      <div
        style={{
          opacity: progress,
          color: COLORS.accent,
          fontSize: 28,
          lineHeight: 1,
        }}
      >
        ↓
      </div>
      {label && (
        <div
          style={{
            opacity: progress,
            fontFamily: FONT.mono,
            fontSize: 20,
            color: COLORS.textMuted,
          }}
        >
          {label}
        </div>
      )}
    </div>
  );
};

export const SceneArchitecture = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, fps * 0.5], [0, 1], {
    extrapolateRight: "clamp",
  });
  const titleY = interpolate(frame, [0, fps * 0.5], [-20, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  const NODE_DELAY = fps * 1.0; // first node appears at 1s
  const ARROW_GAP = fps * 1.2;  // each arrow+node pair spaced 1.2s

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 20%, #0d1b2a 0%, ${COLORS.bg} 70%)`,
        fontFamily: FONT.sans,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "0 60px",
      }}
    >
      {/* Title */}
      <div
        style={{
          position: "absolute",
          top: 110,
          opacity: titleOpacity,
          transform: `translateY(${titleY}px)`,
          textAlign: "center",
        }}
      >
        <div
          style={{
            fontFamily: FONT.mono,
            fontSize: 28,
            color: COLORS.accent,
            letterSpacing: "0.2em",
            textTransform: "uppercase",
          }}
        >
          How it works
        </div>
        <div
          style={{
            fontSize: 52,
            fontWeight: 800,
            color: COLORS.textPrimary,
            marginTop: 8,
          }}
        >
          One seamless pipeline
        </div>
      </div>

      {/* Pipeline flow */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 0,
          marginTop: 60,
        }}
      >
        <ArchNode
          icon="🔄"
          label="Infinity Flow S1+"
          sublabel="hardware"
          color={COLORS.accent}
          frame={frame}
          fps={fps}
          delay={NODE_DELAY}
        />

        <FlowArrow
          frame={frame}
          fps={fps}
          delay={NODE_DELAY + fps * 0.5}
          label="WebSocket"
        />

        <ArchNode
          icon="☁️"
          label="FlowQ Cloud"
          sublabel="api.infinityflow3d.com"
          color="#818cf8"
          frame={frame}
          fps={fps}
          delay={NODE_DELAY + ARROW_GAP}
        />

        <FlowArrow
          frame={frame}
          fps={fps}
          delay={NODE_DELAY + ARROW_GAP + fps * 0.5}
          label="HTTP/WS"
        />

        <ArchNode
          icon="🌙"
          label="Moonraker"
          sublabel="component"
          color="#c084fc"
          frame={frame}
          fps={fps}
          delay={NODE_DELAY + ARROW_GAP * 2}
        />

        <FlowArrow
          frame={frame}
          fps={fps}
          delay={NODE_DELAY + ARROW_GAP * 2 + fps * 0.5}
          label="G-code"
        />

        <ArchNode
          icon="🐍"
          label="Klipper"
          sublabel="extras module"
          color="#86efac"
          frame={frame}
          fps={fps}
          delay={NODE_DELAY + ARROW_GAP * 3}
        />

        <FlowArrow
          frame={frame}
          fps={fps}
          delay={NODE_DELAY + ARROW_GAP * 3 + fps * 0.5}
        />

        <ArchNode
          icon="🖥️"
          label="Fluidd / Mainsail"
          sublabel="virtual sensors"
          color={COLORS.orange}
          frame={frame}
          fps={fps}
          delay={NODE_DELAY + ARROW_GAP * 4}
        />
      </div>
    </AbsoluteFill>
  );
};
