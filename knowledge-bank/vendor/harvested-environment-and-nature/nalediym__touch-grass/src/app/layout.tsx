import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Touch Grass — A Claude Code plugin that reminds you to go outside",
  description:
    "A Claude Code plugin + MCP server that teaches your AI coding agent to remind you to go outside. Weather-aware, sunset-aware, session-aware. Never interrupts your flow.",
  metadataBase: new URL("https://touch-grass-xi.vercel.app"),
  keywords: [
    "claude code plugin",
    "claude code pomodoro",
    "mcp server",
    "model context protocol",
    "ai break reminder",
    "developer wellness",
    "coding break reminder",
    "claude code hooks",
    "touch grass",
    "outdoor reminder",
  ],
  openGraph: {
    title: "Touch Grass — AI agent that reminds you to touch grass",
    description:
      "A Claude Code plugin + MCP server. Your coding agent gets live weather, sunset timing, and streak state at every session start, and nudges you outside at natural pauses.",
    siteName: "Touch Grass",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Touch Grass — AI agent that reminds you to touch grass",
    description:
      "Claude Code plugin + MCP server. Live weather, sunset timing, session telemetry — injected into your agent's context automatically.",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Touch Grass",
  },
  other: {
    "mobile-web-app-capable": "yes",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
