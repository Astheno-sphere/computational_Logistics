"use server";

import { cookies } from "next/headers";
import { eq, desc } from "drizzle-orm";
import { isDbConfigured, getDb } from "./db";
import { users, activities } from "./db/schema";
import { getActivityType, getLevel } from "./game";

export async function getCurrentUser() {
  const cookieStore = await cookies();
  const userId = cookieStore.get("tg-user-id")?.value;
  if (!userId || !isDbConfigured()) return null;

  const db = getDb();
  const user = await db.query.users.findFirst({
    where: eq(users.id, userId),
  });
  return user ?? null;
}

export async function createUser(displayName: string, emojiAvatar: string) {
  if (!isDbConfigured()) return null;

  const db = getDb();
  const [user] = await db
    .insert(users)
    .values({ displayName, emojiAvatar })
    .returning();

  const cookieStore = await cookies();
  cookieStore.set("tg-user-id", user.id, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 365,
  });

  return user;
}

export async function logActivity(activityType: string, note?: string) {
  const cookieStore = await cookies();
  const userId = cookieStore.get("tg-user-id")?.value;
  if (!userId || !isDbConfigured()) return null;

  const db = getDb();
  const activityInfo = getActivityType(activityType);
  const points = activityInfo.points;

  const user = await db.query.users.findFirst({
    where: eq(users.id, userId),
  });
  if (!user) return null;

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

  const [activity] = await db
    .insert(activities)
    .values({
      userId,
      activityType,
      note: note || null,
      pointsEarned: points,
    })
    .returning();

  await db
    .update(users)
    .set({
      totalPoints: newPoints,
      currentStreak: newStreak,
      longestStreak: newLongest,
      lastActivityDate: today,
    })
    .where(eq(users.id, userId));

  const oldLevel = getLevel(user.totalPoints);
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

export async function getDashboard() {
  const cookieStore = await cookies();
  const userId = cookieStore.get("tg-user-id")?.value;
  if (!userId || !isDbConfigured()) return null;

  const db = getDb();
  const user = await db.query.users.findFirst({
    where: eq(users.id, userId),
  });
  if (!user) return null;

  const recentActivities = await db.query.activities.findMany({
    where: eq(activities.userId, userId),
    orderBy: [desc(activities.createdAt)],
    limit: 10,
  });

  return {
    user,
    level: getLevel(user.totalPoints),
    recentActivities,
  };
}

export async function getFeed() {
  if (!isDbConfigured()) return [];

  const db = getDb();
  const feedItems = await db
    .select({
      id: activities.id,
      activityType: activities.activityType,
      note: activities.note,
      pointsEarned: activities.pointsEarned,
      createdAt: activities.createdAt,
      userName: users.displayName,
      userEmoji: users.emojiAvatar,
    })
    .from(activities)
    .innerJoin(users, eq(activities.userId, users.id))
    .orderBy(desc(activities.createdAt))
    .limit(50);

  return feedItems;
}
