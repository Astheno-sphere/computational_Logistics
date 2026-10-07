import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 180,
          height: 180,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #166534, #22c55e)",
          borderRadius: 40,
          fontSize: 100,
        }}
      >
        🌿
      </div>
    ),
    { ...size }
  );
}
