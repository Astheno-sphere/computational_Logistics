export const ACTIVITY_TYPES = [
  { id: "walk", label: "Walk", emoji: "🚶", points: 10, description: "A nice walk outside" },
  { id: "hike", label: "Hike", emoji: "🥾", points: 25, description: "Hit the trails" },
  { id: "park", label: "Park Hangs", emoji: "🌳", points: 15, description: "Chilling at the park" },
  { id: "garden", label: "Gardening", emoji: "🌻", points: 20, description: "Getting your hands dirty" },
  { id: "beach", label: "Beach", emoji: "🏖️", points: 20, description: "Sand between your toes" },
  { id: "picnic", label: "Picnic", emoji: "🧺", points: 15, description: "Eating outside hits different" },
  { id: "sports", label: "Sports", emoji: "⚽", points: 25, description: "Moving your body outdoors" },
  { id: "vibe", label: "Just Vibing", emoji: "☀️", points: 10, description: "Touched grass. That's it." },
] as const;

export type ActivityType = (typeof ACTIVITY_TYPES)[number]["id"];

export const LEVELS = [
  { level: 1, name: "Couch Potato", emoji: "🥔", minPoints: 0 },
  { level: 2, name: "Porch Sitter", emoji: "🪑", minPoints: 50 },
  { level: 3, name: "Park Visitor", emoji: "🌿", minPoints: 150 },
  { level: 4, name: "Nature Walker", emoji: "🚶", minPoints: 350 },
  { level: 5, name: "Grass Toucher", emoji: "🌱", minPoints: 700 },
  { level: 6, name: "Trail Blazer", emoji: "🥾", minPoints: 1200 },
  { level: 7, name: "Nature Lover", emoji: "🌸", minPoints: 2000 },
  { level: 8, name: "Wilderness Expert", emoji: "🏔️", minPoints: 3500 },
  { level: 9, name: "Grass Whisperer", emoji: "🌾", minPoints: 6000 },
  { level: 10, name: "One With Nature", emoji: "🌍", minPoints: 10000 },
] as const;

export const AVATAR_OPTIONS = [
  "🌱", "🌿", "🌳", "🌻", "🌸", "🍀", "🌺", "🪴", "🌾", "🍃", "🦋", "🐝", "🌈", "☀️", "🌙",
];

export function getLevel(points: number) {
  let current: (typeof LEVELS)[number] = LEVELS[0];
  for (const level of LEVELS) {
    if (points >= level.minPoints) current = level;
    else break;
  }
  const nextLevel = LEVELS.find((l) => l.level === current.level + 1);
  const progress = nextLevel
    ? (points - current.minPoints) / (nextLevel.minPoints - current.minPoints)
    : 1;
  return {
    ...current,
    progress,
    nextLevel: nextLevel ?? null,
    totalPoints: points,
    pointsToNext: nextLevel ? nextLevel.minPoints - points : 0,
  };
}

export function getActivityType(id: string) {
  return ACTIVITY_TYPES.find((a) => a.id === id) ?? ACTIVITY_TYPES[0];
}

export function formatTimeAgo(date: Date): string {
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return date.toLocaleDateString();
}
