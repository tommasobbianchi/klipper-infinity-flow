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

type SensorCardProps = {
  slot: string;
  state: string;
  color: string;
  frame: number;
  fps: number;
  delay: number;
};

const SensorCard: React.FC<SensorCardProps> = ({
  slot,
  state,
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
  });
  const opacity = interpolate(localFrame, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Pulse ring
  const ringScale = interpolate(
    (frame % Math.round(fps * 1.5)) / Math.round(fps * 1.5),
    [0, 1],
    [1, 2.4],
    { extrapolateRight: "clamp" }
  );
  const ringOpacity = interpolate(
    (frame % Math.round(fps * 1.5)) / Math.round(fps * 1.5),
    [0, 0.6, 1],
    [0.6, 0.2, 0],
    { extrapolateRight: "clamp" }
  );

  return (
    <div
      style={{
        transform: `scale(${sc})`,
        opacity,
        background: COLORS.bgCard,
        border: `1.5px solid ${COLORS.bgCardBorder}`,
        borderRadius: 28,
        padding: "48px 56px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 20,
        minWidth: 360,
        boxShadow: `0 8px 40px ${color}18`,
      }}
    >
      {/* Status dot with pulse */}
      <div style={{ position: "relative", width: 56, height: 56 }}>
        {/* Pulse ring */}
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            width: 56,
            height: 56,
            marginTop: -28,
            marginLeft: -28,
            borderRadius: "50%",
            background: color,
            transform: `scale(${ringScale})`,
            opacity: ringOpacity * (localFrame > 0 ? 1 : 0),
          }}
        />
        {/* Main dot */}
        <div
          style={{
            position: "absolute",
            inset: 8,
            borderRadius: "50%",
            background: color,
            boxShadow: `0 0 24px ${color}`,
          }}
        />
      </div>

      {/* Slot label */}
      <div
        style={{
          fontFamily: FONT.sans,
          fontSize: 36,
          fontWeight: 700,
          color: COLORS.textPrimary,
        }}
      >
        Slot {slot}
      </div>

      {/* State chip */}
      <div
        style={{
          background: `${color}20`,
          border: `1px solid ${color}60`,
          borderRadius: 100,
          padding: "10px 28px",
          fontFamily: FONT.mono,
          fontSize: 28,
          color,
          fontWeight: 600,
        }}
      >
        {state}
      </div>
    </div>
  );
};

export const SceneSensors = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, fps * 0.6], [0, 1], {
    extrapolateRight: "clamp",
  });

  // At t=5s slot B transitions from "Ready" to "Empty"
  const slotBTransitionFrame = fps * 5;
  const slotBSwitching = frame >= slotBTransitionFrame;

  // Swap notice appears when slot B empties
  const swapOpacity = interpolate(
    frame,
    [slotBTransitionFrame, slotBTransitionFrame + fps * 0.8],
    [0, 1],
    { extrapolateRight: "clamp", extrapolateLeft: "clamp" }
  );
  const swapY = interpolate(
    frame,
    [slotBTransitionFrame, slotBTransitionFrame + fps * 0.8],
    [20, 0],
    {
      extrapolateRight: "clamp",
      extrapolateLeft: "clamp",
      easing: Easing.out(Easing.quad),
    }
  );

  // Description text fades in
  const descOpacity = interpolate(frame, [fps * 0.8, fps * 1.6], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 30%, #0d1b0e 0%, ${COLORS.bg} 65%)`,
        fontFamily: FONT.sans,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-start",
        paddingTop: 130,
        padding: "130px 60px 60px",
      }}
    >
      {/* Title */}
      <div style={{ opacity: titleOpacity, textAlign: "center", marginBottom: 24 }}>
        <div
          style={{
            fontFamily: FONT.mono,
            fontSize: 28,
            color: COLORS.green,
            letterSpacing: "0.2em",
            textTransform: "uppercase",
          }}
        >
          Live in your dashboard
        </div>
        <div
          style={{
            fontSize: 56,
            fontWeight: 800,
            color: COLORS.textPrimary,
            marginTop: 10,
            lineHeight: 1.1,
          }}
        >
          Virtual filament
          <br />
          sensors
        </div>
      </div>

      {/* Sensor cards */}
      <div
        style={{
          display: "flex",
          flexDirection: "row",
          gap: 32,
          marginTop: 48,
          justifyContent: "center",
        }}
      >
        <SensorCard
          slot="A"
          state="Ready"
          color={COLORS.green}
          frame={frame}
          fps={fps}
          delay={fps * 0.5}
        />
        <SensorCard
          slot="B"
          state={slotBSwitching ? "Empty" : "Ready"}
          color={slotBSwitching ? COLORS.red : COLORS.green}
          frame={frame}
          fps={fps}
          delay={fps * 0.8}
        />
      </div>

      {/* Swap notification */}
      <div
        style={{
          opacity: swapOpacity,
          transform: `translateY(${swapY}px)`,
          marginTop: 56,
          background: `${COLORS.orange}18`,
          border: `1.5px solid ${COLORS.orange}50`,
          borderRadius: 20,
          padding: "28px 48px",
          display: "flex",
          alignItems: "center",
          gap: 20,
        }}
      >
        <div style={{ fontSize: 40 }}>⚠️</div>
        <div>
          <div
            style={{
              fontFamily: FONT.sans,
              fontWeight: 700,
              fontSize: 32,
              color: COLORS.orange,
            }}
          >
            Slot B exhausted
          </div>
          <div
            style={{
              fontFamily: FONT.mono,
              fontSize: 24,
              color: COLORS.textSecondary,
              marginTop: 6,
            }}
          >
            Slot A feeding — swap in progress
          </div>
        </div>
      </div>

      {/* Description */}
      <div
        style={{
          opacity: descOpacity,
          marginTop: 48,
          textAlign: "center",
          fontSize: 34,
          color: COLORS.textSecondary,
          lineHeight: 1.5,
          maxWidth: 820,
        }}
      >
        No dummy pins. No extra config.
        <br />
        Fluidd and Mainsail see them natively.
      </div>
    </AbsoluteFill>
  );
};
