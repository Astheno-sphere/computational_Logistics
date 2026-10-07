import { getLevel, getActivityType } from "./game";
import type { User, Activity, DashboardData, LogResult } from "./types";

const USER_KEY = "touch-grass-user";
const ACTIVITIES_KEY = "touch-grass-activities";

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  const data = localStorage.getItem(USER_KEY);
  if (!data) return null;
  const user = JSON.parse(data);
  user.createdAt = new Date(user.createdAt);
  return user;
}

export function createStoredUser(
  displayName: string,
  emojiAvatar: string
): User {
  const user: User = {
    id: crypto.randomUUID(),
    displayName,
    emojiAvatar,
    totalPoints: 0,
    currentStreak: 0,
    longestStreak: 0,
    lastActivityDate: null,
    createdAt: new Date(),
  };
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  return user;
}

export function getStoredActivities(): Activity[] {
  if (typeof window === "undefined") return [];
  const data = localStorage.getItem(ACTIVITIES_KEY);
  if (!data) return [];
  const activities = JSON.parse(data);
  return activities.map((a: Activity) => ({
    ...a,
    createdAt: new Date(a.createdAt),
  }));
}

export function logStoredActivity(
  activityType: string,
  note?: string
): LogResult | null {
  const user = getStoredUser();
  if (!user) return null;

  const activityInfo = getActivityType(activityType);
  const points = activityInfo.points;

  const today = new Date().toISOString().split("T")[0];
  const yesterday = new Date(Date.now() - 86400000)
    .toISOString()
    .split("T")[0];

  let newStreak = user.currentStreak;
  if (user.lastActivityDate === today) {
    // Already logged today, keep streak
  } else if (user.lastActivityDate === yesterday) {
    newStreak = user.currentStreak + 1;
  } else {
    newStreak = 1;
  }

  const newLongest = Math.max(newStreak, user.longestStreak);
  const newPoints = user.totalPoints + points;
  const oldLevel = getLevel(user.totalPoints);

  const activity: Activity = {
    id: crypto.randomUUID(),
    userId: user.id,
    activityType,
    note: note || null,
    pointsEarned: points,
    createdAt: new Date(),
  };

  // Save activity
  const activities = getStoredActivities();
  activities.unshift(activity);
  localStorage.setItem(ACTIVITIES_KEY, JSON.stringify(activities));

  // Update user
  user.totalPoints = newPoints;
  user.currentStreak = newStreak;
  user.longestStreak = newLongest;
  user.lastActivityDate = today;
  localStorage.setItem(USER_KEY, JSON.stringify(user));

  const newLevel = getLevel(newPoints);

  return {
    activity,
    pointsEarned: points,
    newTotal: newPoints,
    streak: newStreak,
    leveledUp: newLevel.level > oldLevel.level,
    newLevel,
  };
}

export function getStoredDashboard(): DashboardData | null {
  const user = getStoredUser();
  if (!user) return null;

  return {
    user,
    level: getLevel(user.totalPoints),
    recentActivities: getStoredActivities().slice(0, 20),
  };
}
