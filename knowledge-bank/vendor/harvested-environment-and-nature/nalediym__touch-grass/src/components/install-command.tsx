"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

export function InstallCommand({
  command,
  label,
}: {
  command: string;
  label?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  }

  return (
    <div className="w-full max-w-xl">
      {label && (
        <p className="text-xs text-muted-foreground mb-2 font-mono uppercase tracking-wider text-left">
          {label}
        </p>
      )}
      <div className="bg-card border rounded-xl px-4 py-3 flex items-center gap-3 font-mono text-sm shadow-md">
        <span className="text-primary">$</span>
        <code className="flex-1 text-left truncate">{command}</code>
        <button
          onClick={copy}
          aria-label="Copy install command"
          className="shrink-0 p-2 rounded-md hover:bg-muted transition-colors cursor-pointer"
        >
          {copied ? (
            <Check className="h-4 w-4 text-primary" />
          ) : (
            <Copy className="h-4 w-4 text-muted-foreground" />
          )}
        </button>
      </div>
    </div>
  );
}
