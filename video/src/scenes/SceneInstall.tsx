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

type StepProps = {
  number: number;
  title: string;
  code: string;
  frame: number;
  fps: number;
  delay: number;
  color: string;
};

const InstallStep: React.FC<StepProps> = ({
  number,
  title,
  code,
  frame,
  fps,
  delay,
  color,
}) => {
  const localFrame = frame - delay;
  const sc = spring({
    frame: localFrame,
    fps,
    config: { damping: 16, stiffness: 160 },
  });
  const opacity = interpolate(localFrame, [0, 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const translateX = interpolate(localFrame, [0, fps * 0.6], [-60, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  return (
    <div
      style={{
        opacity,
        transform: `translateX(${translateX}px)`,
        display: "flex",
        flexDirection: "row",
        alignItems: "flex-start",
        gap: 28,
        width: "100%",
      }}
    >
      {/* Step number */}
      <div
        style={{
          width: 72,
          height: 72,
          borderRadius: "50%",
          background: `${color}20`,
          border: `2px solid ${color}70`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: FONT.mono,
          fontSize: 32,
          fontWeight: 700,
          color,
          flexShrink: 0,
        }}
      >
        {number}
      </div>

      {/* Content */}
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontFamily: FONT.sans,
            fontSize: 34,
            fontWeight: 700,
            color: COLORS.textPrimary,
            marginBottom: 10,
          }}
        >
          {title}
        </div>
        <div
          style={{
            fontFamily: FONT.mono,
            fontSize: 26,
            color: color,
            background: `${COLORS.bgCard}`,
            border: `1px solid ${COLORS.bgCardBorder}`,
            borderRadius: 12,
            padding: "14px 20px",
          }}
        >
          $ {code}
        </div>
      </div>
    </div>
  );
};

export const SceneInstall = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, fps * 0.5], [0, 1], {
    extrapolateRight: "clamp",
  });
  const titleY = interpolate(frame, [0, fps * 0.5], [-20, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  const steps = [
    {
      number: 1,
      title: "Clone & install",
      code: "./install.sh",
      color: COLORS.accent,
      delay: fps * 0.8,
    },
    {
      number: 2,
      title: "Get your token",
      code: "python3 flowq_setup_token.py",
      color: "#c084fc",
      delay: fps * 2.0,
    },
    {
      number: 3,
      title: "Restart services",
      code: "sudo systemctl restart moonraker klipper",
      color: COLORS.green,
      delay: fps * 3.2,
    },
  ];

  // Badge that appears at the end
  const badgeOpacity = interpolate(frame, [fps * 5.5, fps * 6.5], [0, 1], {
    extrapolateRight: "clamp",
  });
  const badgeScale = spring({
    frame: frame - fps * 5.5,
    fps,
    config: { damping: 12, stiffness: 200 },
  });

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 20%, #0a1a2e 0%, ${COLORS.bg} 65%)`,
        fontFamily: FONT.sans,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-start",
        padding: "120px 80px 60px",
      }}
    >
      {/* Title */}
      <div
        style={{
          opacity: titleOpacity,
          transform: `translateY(${titleY}px)`,
          textAlign: "center",
          marginBottom: 60,
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
          Setup
        </div>
        <div
          style={{
            fontSize: 62,
            fontWeight: 800,
            color: COLORS.textPrimary,
            marginTop: 8,
            lineHeight: 1.1,
          }}
        >
          3 steps.
          <br />
          <span style={{ color: COLORS.accent }}>That's it.</span>
        </div>
      </div>

      {/* Steps */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 36,
          width: "100%",
        }}
      >
        {steps.map((step) => (
          <InstallStep
            key={step.number}
            number={step.number}
            title={step.title}
            code={step.code}
            color={step.color}
            frame={frame}
            fps={fps}
            delay={step.delay}
          />
        ))}
      </div>

      {/* "Zero hardware mods" badge */}
      <div
        style={{
          opacity: badgeOpacity,
          transform: `scale(${badgeScale})`,
          marginTop: 64,
          background: `${COLORS.green}15`,
          border: `1.5px solid ${COLORS.green}50`,
          borderRadius: 100,
          padding: "18px 48px",
          display: "flex",
          alignItems: "center",
          gap: 16,
        }}
      >
        <div style={{ fontSize: 34 }}>✅</div>
        <div
          style={{
            fontFamily: FONT.sans,
            fontSize: 30,
            fontWeight: 600,
            color: COLORS.green,
          }}
        >
          No hardware modifications needed
        </div>
      </div>
    </AbsoluteFill>
  );
};
