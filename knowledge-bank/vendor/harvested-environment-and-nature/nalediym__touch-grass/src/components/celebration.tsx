"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import type { LogResult } from "@/lib/types";
import { getActivityShareText, share } from "@/lib/share";
import { getActivityType } from "@/lib/game";
import { Button } from "@/components/ui/button";

const PARTICLE_COLORS = [
  "#4ade80",
  "#22c55e",
  "#facc15",
  "#fb923c",
  "#86efac",
  "#a3e635",
];

export function Celebration({
  data,
  onDismiss,
}: {
  data: LogResult;
  onDismiss: () => void;
}) {
  const [showShare, setShowShare] = useState(false);

  const [particles] = useState(() =>
    Array.from({ length: 24 }, (_, i) => ({
      id: i,
      angle: (i / 24) * 360,
      distance: 80 + Math.random() * 120,
      size: 6 + Math.random() * 10,
      color: PARTICLE_COLORS[i % PARTICLE_COLORS.length],
      delay: Math.random() * 0.2,
      borderRadius: Math.random() > 0.5 ? "50%" : "2px",
    }))
  );

  const activityInfo = getActivityType(data.activity.activityType);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={(e) => {
        if (e.target === e.currentTarget && showShare) onDismiss();
      }}
    >
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: showShare ? 0.6 : 0 }}
        className="absolute inset-0 bg-black"
      />

      {/* Screen flash */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: [0, 0.15, 0] }}
        transition={{ duration: 0.6 }}
        className="absolute inset-0 bg-primary pointer-events-none"
      />

      {/* Particles */}
      <div className="pointer-events-none">
        {particles.map((p) => (
          <motion.div
            key={p.id}
            initial={{ scale: 0, x: 0, y: 0, opacity: 1 }}
            animate={{
              scale: [0, 1.2, 0],
              x: Math.cos((p.angle * Math.PI) / 180) * p.distance,
              y: Math.sin((p.angle * Math.PI) / 180) * p.distance,
              opacity: [1, 1, 0],
            }}
            transition={{ duration: 1.2, delay: p.delay, ease: "easeOut" }}
            style={{
              width: p.size,
              height: p.size,
              backgroundColor: p.color,
              borderRadius: p.borderRadius,
              position: "absolute",
            }}
          />
        ))}
      </div>

      {/* Points text */}
      <motion.div
        initial={{ scale: 0, y: 0 }}
        animate={{ scale: [0, 1.6, 1], y: showShare ? -140 : -50 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="text-5xl font-black text-primary drop-shadow-lg pointer-events-none"
      >
        +{data.pointsEarned}
      </motion.div>

      {/* Level up announcement */}
      {data.leveledUp && (
        <motion.div
          initial={{ scale: 0, y: 30, opacity: 0 }}
          animate={{ scale: [0, 1.3, 1], y: showShare ? -80 : 30, opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.4, ease: "easeOut" }}
          className="absolute text-center pointer-events-none"
        >
          <p className="text-3xl font-black">LEVEL UP!</p>
          <p className="text-xl mt-1">
            {data.newLevel.emoji} {data.newLevel.name}
          </p>
        </motion.div>
      )}

      {/* Share card — appears after particles */}
      <motion.div
        initial={{ opacity: 0, y: 40, scale: 0.9 }}
        animate={{ opacity: 1, y: 20, scale: 1 }}
        transition={{ delay: 1.2, duration: 0.4, ease: "easeOut" }}
        onAnimationComplete={() => setShowShare(true)}
        className="absolute bg-card border rounded-2xl p-6 shadow-2xl w-[320px] text-center"
      >
        <p className="text-sm text-muted-foreground mb-1">You just logged</p>
        <p className="text-2xl font-bold mb-1">
          {activityInfo.emoji} {activityInfo.label}
        </p>
        <p className="text-sm text-muted-foreground mb-4">
          🔥 {data.streak}-day streak · 💎 {data.newTotal} pts total
        </p>

        <div className="flex gap-2">
          <Button
            className="flex-1"
            onClick={() => share(getActivityShareText(data))}
          >
            Share 🌿
          </Button>
          <Button variant="secondary" className="flex-1" onClick={onDismiss}>
            Done
          </Button>
        </div>
      </motion.div>
    </motion.div>
  );
}
