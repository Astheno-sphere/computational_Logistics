import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { InstallCommand } from "@/components/install-command";
import { NudgeDemo } from "@/components/nudge-demo";

const GITHUB_URL = "https://github.com/nalediym/touch-grass";
const PLUGIN_INSTALL = "/plugin install nalediym/touch-grass";

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Hero */}
      <section className="flex-1 flex flex-col items-center justify-center min-h-[90vh] px-6 text-center relative overflow-hidden">
        <div className="absolute inset-0 -z-10 select-none" aria-hidden>
          <span
            className="absolute top-[12%] left-[8%] text-6xl opacity-10 animate-bounce"
            style={{ animationDuration: "4s" }}
          >
            🌿
          </span>
          <span
            className="absolute top-[22%] right-[10%] text-5xl opacity-10 animate-bounce"
            style={{ animationDuration: "5s", animationDelay: "1s" }}
          >
            🌳
          </span>
          <span
            className="absolute bottom-[25%] left-[12%] text-4xl opacity-10 animate-bounce"
            style={{ animationDuration: "4.5s", animationDelay: "2s" }}
          >
            🌻
          </span>
        </div>

        <div className="text-7xl mb-6">🌿</div>
        <h1 className="text-5xl sm:text-7xl font-bold tracking-tight mb-4">
          Touch Grass
        </h1>
        <p className="text-xl sm:text-2xl text-muted-foreground max-w-xl mb-2">
          A plugin that teaches your AI agent to remind you to go outside.
        </p>
        <p className="text-base sm:text-lg text-muted-foreground max-w-lg mb-10">
          Weather-aware. Sunset-aware. Session-aware. Never interrupts your
          flow.
        </p>

        <InstallCommand command={PLUGIN_INSTALL} label="Claude Code" />

        <div className="flex flex-wrap gap-3 mt-6 justify-center">
          <Link href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
            <Button variant="outline" className="cursor-pointer">
              View on GitHub
            </Button>
          </Link>
          <Link href="/play">
            <Button variant="ghost" className="cursor-pointer">
              Try the web version →
            </Button>
          </Link>
        </div>
      </section>

      {/* What your agent sees */}
      <section className="max-w-3xl mx-auto px-6 py-16 w-full">
        <h2 className="text-3xl sm:text-4xl font-bold text-center mb-3">
          What your agent sees
        </h2>
        <p className="text-center text-muted-foreground mb-10 max-w-lg mx-auto">
          Every session starts with a context injection pulled from live
          weather, sunset timing, and your grass streak. Your agent decides
          when and how to nudge.
        </p>
        <NudgeDemo />
      </section>

      {/* How it works */}
      <section className="max-w-4xl mx-auto px-6 py-16 w-full">
        <h2 className="text-3xl sm:text-4xl font-bold text-center mb-10">
          How it works
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card>
            <CardContent className="pt-6">
              <div className="text-sm font-mono text-muted-foreground mb-3">
                01
              </div>
              <div className="text-3xl mb-3">🔌</div>
              <h3 className="font-semibold text-lg mb-2">Install the plugin</h3>
              <p className="text-sm text-muted-foreground">
                One command. Bundles a SessionStart hook, MCP server, and agent
                skill.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-sm font-mono text-muted-foreground mb-3">
                02
              </div>
              <div className="text-3xl mb-3">📡</div>
              <h3 className="font-semibold text-lg mb-2">Ambient context</h3>
              <p className="text-sm text-muted-foreground">
                Your agent gets real weather, sunset timing, and streak state
                the moment a session starts.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-sm font-mono text-muted-foreground mb-3">
                03
              </div>
              <div className="text-3xl mb-3">🌿</div>
              <h3 className="font-semibold text-lg mb-2">Smart nudges</h3>
              <p className="text-sm text-muted-foreground">
                At natural pauses, your agent suggests you step outside.
                Specific, timely, never preachy.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* What's in the box */}
      <section className="max-w-4xl mx-auto px-6 py-16 w-full">
        <h2 className="text-3xl sm:text-4xl font-bold text-center mb-10">
          What&apos;s in the box
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <FeatureItem emoji="☀️" title="Weather-aware">
            Live temperature and conditions from open-meteo. Skips nudging when
            the weather sucks.
          </FeatureItem>
          <FeatureItem emoji="🌅" title="Golden hour detection">
            Pushes harder when sunset is imminent. Golden-hour-specific activity
            suggestions.
          </FeatureItem>
          <FeatureItem emoji="🔥" title="Streak tracking">
            Local file tracks consecutive days outside. Your agent reminds you
            before the streak dies.
          </FeatureItem>
          <FeatureItem emoji="⏰" title="Session telemetry">
            Detects when you&apos;ve been coding all day and firms up the
            nudge.
          </FeatureItem>
          <FeatureItem emoji="🤖" title="Cross-agent">
            MCP server works in Claude Code, Cursor, Claude Desktop, Codex. The
            hook is Claude Code bonus for proactive nudging.
          </FeatureItem>
          <FeatureItem emoji="🔒" title="Local and private">
            Everything in <code className="text-xs">~/.touch-grass/</code>. No
            accounts, no API keys, no tracking.
          </FeatureItem>
        </div>
      </section>

      {/* MCP tools */}
      <section className="max-w-3xl mx-auto px-6 py-16 w-full">
        <h2 className="text-3xl sm:text-4xl font-bold text-center mb-3">
          MCP tools exposed to your agent
        </h2>
        <p className="text-center text-muted-foreground mb-10 max-w-lg mx-auto">
          Any MCP-compatible agent can call these directly.
        </p>
        <Card>
          <CardContent className="pt-6 space-y-4 font-mono text-sm">
            <ToolRow
              name="check_grass_conditions"
              description="Weather, temperature, minutes to sunset, streak state"
            />
            <ToolRow
              name="suggest_activity"
              description="Random activity recommendation (golden-hour-aware)"
            />
            <ToolRow
              name="log_touch_grass"
              description="Records that the user went outside, updates streak"
            />
            <ToolRow
              name="get_stats"
              description="Current streak, longest, total, session counts"
            />
          </CardContent>
        </Card>
      </section>

      {/* Final CTA */}
      <section className="max-w-2xl mx-auto px-6 py-16 w-full text-center">
        <div className="text-5xl mb-4">🌿</div>
        <h2 className="text-3xl sm:text-4xl font-bold mb-4">
          Ready to touch grass?
        </h2>
        <p className="text-muted-foreground mb-8">
          Install the plugin. Start coding. Let your agent do the reminding.
        </p>
        <div className="flex justify-center">
          <InstallCommand command={PLUGIN_INSTALL} />
        </div>
      </section>

      {/* Footer */}
      <footer className="text-center py-8 text-sm text-muted-foreground border-t">
        Touch Grass — because your screen will be here when you get back 🌱
      </footer>
    </div>
  );
}

function FeatureItem({
  emoji,
  title,
  children,
}: {
  emoji: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-4">
      <div className="text-3xl shrink-0">{emoji}</div>
      <div>
        <h3 className="font-semibold mb-1">{title}</h3>
        <p className="text-sm text-muted-foreground">{children}</p>
      </div>
    </div>
  );
}

function ToolRow({
  name,
  description,
}: {
  name: string;
  description: string;
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-4 py-2 border-b last:border-b-0">
      <code className="text-primary font-semibold shrink-0 sm:w-56">
        {name}
      </code>
      <span className="text-muted-foreground text-xs sm:text-sm font-sans">
        {description}
      </span>
    </div>
  );
}
