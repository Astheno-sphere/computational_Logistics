"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { logStoredActivity } from "@/lib/storage";
import { ACTIVITY_TYPES, getActivityType, formatTimeAgo } from "@/lib/game";
import { getProgressShareText, share } from "@/lib/share";
import type { DashboardData, LogResult } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Celebration } from "@/components/celebration";
import { cn } from "@/lib/utils";

export function PlayView({
  dashboard,
  onRefresh,
}: {
  dashboard: DashboardData;
  onRefresh: () => void;
}) {
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [celebration, setCelebration] = useState<LogResult | null>(null);

  const { user, level, recentActivities } = dashboard;

  function handleLogActivity() {
    if (!selectedType) return;

    const result = logStoredActivity(selectedType, note || undefined);
    if (result) {
      setCelebration(result);
      setSelectedType(null);
      setNote("");
    }
  }

  return (
    <div className="min-h-screen pb-20">
      <AnimatePresence>
        {celebration && (
          <Celebration
            data={celebration}
            onDismiss={() => {
              setCelebration(null);
              onRefresh();
            }}
          />
        )}
      </AnimatePresence>

      {/* Sticky Header */}
      <header className="sticky top-0 z-10 bg-background/80 backdrop-blur-md border-b">
        <div className="max-w-2xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-3xl">{user.emojiAvatar}</span>
              <div>
                <p className="font-semibold leading-tight">
                  {user.displayName}
                </p>
                <p className="text-sm text-muted-foreground">
                  {level.emoji} {level.name}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-5">
              <div className="text-center">
                <p className="font-bold text-lg leading-tight tabular-nums">
                  {user.currentStreak}
                </p>
                <p className="text-xs text-muted-foreground">Streak</p>
              </div>
              <div className="text-center">
                <p className="font-bold text-lg leading-tight tabular-nums">
                  {user.totalPoints}
                </p>
                <p className="text-xs text-muted-foreground">Points</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-6 space-y-8">
        {/* XP Progress Bar */}
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="font-medium">
              Level {level.level}: {level.name} {level.emoji}
            </span>
            {level.nextLevel && (
              <span className="text-muted-foreground tabular-nums">
                {level.pointsToNext} pts to {level.nextLevel.emoji}{" "}
                {level.nextLevel.name}
              </span>
            )}
          </div>
          <Progress value={level.progress * 100} className="h-3" />
          <Button
            variant="secondary"
            size="sm"
            className="mt-3 w-full"
            onClick={() => share(getProgressShareText(dashboard))}
          >
            Share Your Progress 🌿
          </Button>
        </div>

        {/* Activity Picker */}
        <section>
          <h2 className="text-lg font-semibold mb-3">What did you do?</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {ACTIVITY_TYPES.map((activity) => (
              <motion.button
                key={activity.id}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={() =>
                  setSelectedType(
                    selectedType === activity.id ? null : activity.id
                  )
                }
                className={cn(
                  "flex flex-col items-center gap-1.5 p-4 rounded-xl border-2 transition-colors",
                  selectedType === activity.id
                    ? "border-primary bg-primary/10 shadow-md"
                    : "border-transparent bg-card hover:border-border shadow-sm"
                )}
              >
                <span className="text-3xl">{activity.emoji}</span>
                <span className="text-sm font-medium">{activity.label}</span>
                <Badge variant="secondary" className="text-xs">
                  +{activity.points}
                </Badge>
              </motion.button>
            ))}
          </div>
        </section>

        {/* Note + Submit */}
        <AnimatePresence>
          {selectedType && (
            <motion.section
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="space-y-3 overflow-hidden"
            >
              <Textarea
                placeholder={`How was the ${getActivityType(selectedType).label.toLowerCase()}? (optional)`}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={280}
                rows={2}
                className="resize-none"
              />
              <Button
                size="lg"
                className="w-full text-lg h-14 rounded-xl shadow-lg animate-pulse-glow"
                onClick={handleLogActivity}
              >
                I Touched Grass! 🌿
              </Button>
            </motion.section>
          )}
        </AnimatePresence>

        <Separator />

        {/* Activity Log */}
        <section>
          <h2 className="text-lg font-semibold mb-3">Your Activity Log</h2>
          {recentActivities.length === 0 ? (
            <Card className="p-8 text-center">
              <p className="text-4xl mb-3">🌱</p>
              <p className="font-medium">No activities yet</p>
              <p className="text-sm text-muted-foreground mt-1">
                Log your first outdoor activity above!
              </p>
            </Card>
          ) : (
            <div className="space-y-3">
              {recentActivities.map((item, i) => {
                const activityInfo = getActivityType(item.activityType);
                return (
                  <motion.div
                    key={item.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.03 }}
                  >
                    <Card className="p-4">
                      <div className="flex items-start gap-3">
                        <span className="text-2xl shrink-0">
                          {activityInfo.emoji}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p>
                            <span className="font-semibold">
                              {activityInfo.label}
                            </span>{" "}
                            <span className="text-muted-foreground">
                              —{" "}
                              <span className="font-medium text-primary">
                                +{item.pointsEarned} pts
                              </span>
                            </span>
                          </p>
                          {item.note && (
                            <p className="text-sm text-muted-foreground mt-1 italic">
                              &ldquo;{item.note}&rdquo;
                            </p>
                          )}
                          <p className="text-xs text-muted-foreground mt-1.5">
                            {formatTimeAgo(new Date(item.createdAt))}
                          </p>
                        </div>
                      </div>
                    </Card>
                  </motion.div>
                );
              })}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
