import { ImageResponse } from "next/og";

export const alt = "Touch Grass — A Claude Code plugin that reminds you to go outside";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(145deg, #0a1a0a 0%, #1a3a1a 50%, #0a1a0a 100%)",
          color: "white",
          fontFamily: "system-ui, sans-serif",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Decorative circles */}
        <div
          style={{
            position: "absolute",
            top: -100,
            right: -100,
            width: 400,
            height: 400,
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(74,222,128,0.15) 0%, transparent 70%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: -80,
            left: -80,
            width: 300,
            height: 300,
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(74,222,128,0.1) 0%, transparent 70%)",
          }}
        />

        <div style={{ fontSize: 100, marginBottom: 10 }}>🌿</div>
        <div
          style={{
            fontSize: 72,
            fontWeight: 800,
            letterSpacing: "-2px",
            marginBottom: 8,
          }}
        >
          Touch Grass
        </div>
        <div
          style={{
            fontSize: 28,
            opacity: 0.7,
            marginBottom: 10,
          }}
        >
          A Claude Code plugin for your AI agent
        </div>
        <div
          style={{
            fontSize: 22,
            opacity: 0.6,
            marginBottom: 40,
          }}
        >
          MCP server · SessionStart hook · Skill
        </div>
        <div
          style={{
            display: "flex",
            gap: 40,
            fontSize: 22,
            opacity: 0.9,
          }}
        >
          <span>🌤 Weather-aware</span>
          <span>🌅 Sunset-aware</span>
          <span>⏰ Session-aware</span>
        </div>
      </div>
    ),
    { ...size }
  );
}
