export function NudgeDemo() {
  return (
    <div className="bg-[oklch(0.12_0.03_150)] border border-[oklch(0.28_0.04_150)] rounded-2xl p-6 font-mono text-sm shadow-2xl overflow-auto">
      <div className="flex items-center gap-2 mb-4 text-xs text-[oklch(0.65_0.03_145)]">
        <div className="flex gap-1.5">
          <div className="w-3 h-3 rounded-full bg-red-500/60" />
          <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
          <div className="w-3 h-3 rounded-full bg-green-500/60" />
        </div>
        <span className="ml-2 select-none">
          SessionStart hook → Claude Code context
        </span>
      </div>
      <pre className="text-[oklch(0.85_0.12_140)] whitespace-pre-wrap leading-relaxed">
        <span className="text-[oklch(0.75_0.15_85)]"># 🌿 Touch Grass Conditions</span>
        {"\n\n"}
        <span className="text-[oklch(0.9_0.05_140)]">
          **72°F (22°C), clear**
        </span>{" "}
        outside in Brooklyn.
        {"\n"}
        <span className="text-[oklch(0.75_0.2_55)]">
          ⚠️ SUNSET IN 22 MINUTES.
        </span>{" "}
        This is golden hour. If the user hits any natural pause, push them
        outside NOW.
        {"\n"}
        ✨ It&apos;s genuinely nice out. Suggest 🌅 catch the sunset at the next
        natural pause.
        {"\n\n"}
        <span className="text-[oklch(0.75_0.15_85)]">## User&apos;s Grass Status</span>
        {"\n"}
        🔥 <span className="text-[oklch(0.85_0.15_85)]">3-day streak</span> —
        needs to touch grass today to keep it alive. Don&apos;t let them end
        the session without mentioning it.
        {"\n\n"}
        <span className="text-[oklch(0.75_0.15_85)]">## How to Act on This</span>
        {"\n"}
        At a natural pause (feature complete, bug fixed, tests green, waiting
        for input), gently suggest the user step outside. Match the urgency:
        {"\n\n"}- Sunset soon + nice out → push hard, specific, now
        {"\n"}- Nice day + no grass today → firm nudge at next pause
        {"\n"}- Streak at risk → remind before session ends
      </pre>
    </div>
  );
}
