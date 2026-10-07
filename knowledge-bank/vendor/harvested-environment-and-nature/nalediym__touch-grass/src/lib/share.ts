import { getActivityType } from "./game";
import type { LogResult, DashboardData } from "./types";

function getAppUrl() {
  if (typeof window !== "undefined") return window.location.origin;
  return "https://touch-grass-xi.vercel.app";
}

export function getActivityShareText(result: LogResult): string {
  const activity = getActivityType(result.activity.activityType);
  const lines = [
    `I just touched grass! 🌿`,
    `${activity.emoji} ${activity.label} — +${result.pointsEarned} pts`,
    `🔥 ${result.streak}-day streak`,
  ];
  if (result.leveledUp) {
    lines.push(`🎉 Leveled up to ${result.newLevel.emoji} ${result.newLevel.name}!`);
  }
  lines.push("", getAppUrl());
  return lines.join("\n");
}

export function getProgressShareText(dashboard: DashboardData): string {
  const { user, level } = dashboard;
  return [
    `I'm a ${level.emoji} ${level.name} on Touch Grass 🌿`,
    `🔥 ${user.currentStreak}-day streak | 💎 ${user.totalPoints} pts`,
    ``,
    getAppUrl(),
  ].join("\n");
}

export async function share(text: string) {
  if (navigator.share) {
    try {
      await navigator.share({ text });
      return;
    } catch {
      // User cancelled or error — fall through to Twitter
    }
  }
  // Fallback: open Twitter/X intent
  const url = `https://x.com/intent/post?text=${encodeURIComponent(text)}`;
  window.open(url, "_blank", "noopener,noreferrer");
}
