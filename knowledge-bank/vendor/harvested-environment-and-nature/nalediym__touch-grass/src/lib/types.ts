export type User = {
  id: string;
  displayName: string;
  emojiAvatar: string;
  totalPoints: number;
  currentStreak: number;
  longestStreak: number;
  lastActivityDate: string | null;
  createdAt: Date;
};

export type Activity = {
  id: string;
  userId: string;
  activityType: string;
  note: string | null;
  pointsEarned: number;
  createdAt: Date;
};

export type FeedItem = {
  id: string;
  activityType: string;
  note: string | null;
  pointsEarned: number;
  createdAt: Date;
  userName: string;
  userEmoji: string;
};

export type LevelInfo = {
  level: number;
  name: string;
  emoji: string;
  minPoints: number;
  progress: number;
  nextLevel: { level: number; name: string; emoji: string; minPoints: number } | null;
  totalPoints: number;
  pointsToNext: number;
};

export type DashboardData = {
  user: User;
  level: LevelInfo;
  recentActivities: Activity[];
};

export type LogResult = {
  activity: Activity;
  pointsEarned: number;
  newTotal: number;
  streak: number;
  leveledUp: boolean;
  newLevel: LevelInfo;
};
