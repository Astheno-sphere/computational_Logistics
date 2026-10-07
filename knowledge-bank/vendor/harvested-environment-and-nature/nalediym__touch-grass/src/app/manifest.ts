import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Touch Grass",
    short_name: "Touch Grass",
    description: "Get rewarded for going outside. Build streaks, earn points, level up.",
    start_url: "/play",
    display: "standalone",
    background_color: "#0a1a0a",
    theme_color: "#22c55e",
    icons: [
      {
        src: "/api/pwa-icon?size=192",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/api/pwa-icon?size=512",
        sizes: "512x512",
        type: "image/png",
      },
    ],
  };
}
