"use client";

import { useState } from "react";
import { createStoredUser } from "@/lib/storage";
import { AVATAR_OPTIONS } from "@/lib/game";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function Onboarding({ onComplete }: { onComplete: () => void }) {
  const [name, setName] = useState("");
  const [emoji, setEmoji] = useState("🌱");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    createStoredUser(name.trim(), emoji);
    onComplete();
  }

  return (
    <div className="flex items-center justify-center min-h-screen p-6 bg-gradient-to-b from-background to-secondary/30">
      <Card className="w-full max-w-md p-8 shadow-xl">
        <div className="text-center mb-8">
          <div className="text-6xl mb-4">{emoji}</div>
          <h1 className="text-3xl font-bold tracking-tight">
            Welcome to Touch Grass
          </h1>
          <p className="text-muted-foreground mt-2">
            Pick a name and avatar to get started
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <Input
              placeholder="Your display name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={20}
              required
              className="text-lg h-12"
              autoFocus
            />
          </div>

          <div>
            <p className="text-sm font-medium mb-3">Pick your avatar</p>
            <div className="grid grid-cols-5 gap-2">
              {AVATAR_OPTIONS.map((opt) => (
                <button
                  key={opt}
                  type="button"
                  onClick={() => setEmoji(opt)}
                  className={cn(
                    "text-2xl p-2 rounded-xl transition-all duration-200",
                    emoji === opt
                      ? "bg-primary/15 ring-2 ring-primary scale-110"
                      : "hover:bg-muted hover:scale-105"
                  )}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>

          <Button
            type="submit"
            className="w-full text-lg h-14 rounded-xl"
            disabled={!name.trim()}
          >
            Let&apos;s Touch Grass! 🌿
          </Button>
        </form>
      </Card>
    </div>
  );
}
