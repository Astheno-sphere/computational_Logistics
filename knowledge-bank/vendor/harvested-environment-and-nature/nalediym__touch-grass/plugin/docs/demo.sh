#!/usr/bin/env bash
# Demo script shown in the VHS recording.

green=$'\e[38;2;74;222;128m'
dim=$'\e[38;2;150;170;150m'
gold=$'\e[38;2;250;204;21m'
amber=$'\e[38;2;251;146;60m'
reset=$'\e[0m'
bold=$'\e[1m'

typewriter() {
  local text="$1"
  local delay="${2:-0.03}"
  for (( i=0; i<${#text}; i++ )); do
    printf '%s' "${text:$i:1}"
    sleep "$delay"
  done
}

# Shell prompt + command
printf '%s$%s claude\n' "$dim" "$reset"
sleep 0.5

# Session banner
printf '%s●%s Session started.\n\n' "$green" "$reset"
sleep 0.3

# Hook-injected context block
printf '  %s🌿 Touch Grass Conditions%s\n\n' "$bold" "$reset"
sleep 0.2
printf '  %s63°F (17°C), clear%s outside in Brooklyn.\n' "$bold" "$reset"
sleep 0.15
printf '  %s🌅 Sunset in 38 minutes.%s Golden hour window.\n' "$gold" "$reset"
sleep 0.15
printf "  %s✨ It's genuinely nice out.%s Suggest a walk at the next pause.\n\n" "$green" "$reset"
sleep 0.2
printf "  %sUser's Grass Status%s\n" "$bold" "$reset"
printf '  🔥 %s3-day streak%s — needs to touch grass today to keep it alive.\n\n' "$amber" "$reset"
sleep 0.4

printf '%s─────────────────────────────────────────────%s\n\n' "$dim" "$reset"
sleep 0.3

# User message
printf '%s>%s ' "$dim" "$reset"
typewriter "finish implementing the streak reset logic"
printf '\n\n'
sleep 0.3

# Agent working + nudge
printf '%s●%s Tests green. Streak reset logic is in.\n' "$green" "$reset"
sleep 0.25
printf '%s●%s Before we move on — sunset in %s34 min%s and\n' "$green" "$reset" "$bold" "$reset"
sleep 0.15
printf '  your %s3-day streak%s is on the line. Walk out the door\n' "$amber" "$reset"
sleep 0.15
printf '  now, catch the light, come back for code review.\n\n'
sleep 0.5

# User accepts
printf '%s>%s ' "$dim" "$reset"
typewriter "ok fine"
printf '\n\n'
sleep 0.3

# Log
printf '%s●%s Using %stouch-grass%s → %slog_touch_grass%s(activity="sunset walk")\n' \
  "$green" "$reset" "$bold" "$reset" "$bold" "$reset"
sleep 0.3
printf "  🌿 Logged. Streak: %s%s4 days%s. I'll be here when you get back.\n" "$amber" "$bold" "$reset"
sleep 2
