import { ImageResponse } from "next/og";
import { type NextRequest } from "next/server";

export async function GET(request: NextRequest) {
  const sizeParam = request.nextUrl.searchParams.get("size") || "512";
  const s = parseInt(sizeParam, 10);
  const fontSize = Math.round(s * 0.55);
  const radius = Math.round(s * 0.22);

  return new ImageResponse(
    (
      <div
        style={{
          width: s,
          height: s,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #166534, #22c55e)",
          borderRadius: radius,
          fontSize,
        }}
      >
        🌿
      </div>
    ),
    { width: s, height: s }
  );
}
