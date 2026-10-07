#!/usr/bin/env node
import { checkConditions, recordSessionStart } from "../lib/grass.mjs";
import { generateNudge } from "../lib/nudge.mjs";

async function main() {
  try {
    await recordSessionStart();
    const conditions = await checkConditions();
    const nudge = await generateNudge(conditions);

    if (!nudge) {
      // Silent success — no context to inject
      process.stdout.write(
        JSON.stringify({
          hookSpecificOutput: {
            hookEventName: "SessionStart",
            additionalContext: "",
          },
        })
      );
      return;
    }

    // Claude Code SessionStart hook format: inject as additionalContext
    process.stdout.write(
      JSON.stringify({
        hookSpecificOutput: {
          hookEventName: "SessionStart",
          additionalContext: nudge,
        },
      })
    );
  } catch (err) {
    // Never block the session — fail silently
    process.stderr.write(`touch-grass hook error: ${err.message}\n`);
    process.stdout.write(
      JSON.stringify({
        hookSpecificOutput: {
          hookEventName: "SessionStart",
          additionalContext: "",
        },
      })
    );
  }
}

main();
