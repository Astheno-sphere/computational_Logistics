#!/usr/bin/env bash
# End-to-end runbook: MATSim smoke test -> Molde scenario -> MATSim run -> dynamic-vs-zonal comparison.
#
#   bash skills/matsim-bridge/run_matsim.sh                 # Molde, 1000 agents, 20 iterations, capacity factors 1.0 and 0.1
#   TOWN=kristiansund AGENTS=4000 bash skills/matsim-bridge/run_matsim.sh
#
# Needs: Java 17 (MATSim 2024.0 is built with JDK 17; MATSim 2026.0 needs Java 21 - set MATSIM_VERSION=2026.0 only
# with a Java 21 runtime, and re-check the config module names against that release's examples/equil/config.xml),
# plus Python 3.11+ with numpy, scipy, networkx (pip install -r evidence/fidelity-benchmark/requirements.txt).
# Nothing here is run by the repo's tests; no result exists until you run it.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWN="${TOWN:-molde}"                      # molde | kristiansund
AGENTS="${AGENTS:-1000}"                   # 1..4000 (4000 = the complete static-benchmark OD set)
ITERS="${ITERS:-20}"
SHARES="${SHARES:-1.0 0.1}"                # flow/storage capacity factors: 1.0 ~ uncongested, 0.1 = each agent stands for 10 commuters
MATSIM_VERSION="${MATSIM_VERSION:-2024.0}"
XMX="${XMX:-4g}"
WORK="$HERE/work"                          # downloads + smoke test (git-ignored)
ZIP_URL="https://github.com/matsim-org/matsim-libs/releases/download/${MATSIM_VERSION}/matsim-${MATSIM_VERSION}-release.zip"
JAR="$WORK/matsim-${MATSIM_VERSION}/matsim-${MATSIM_VERSION}.jar"   # its manifest Class-Path pulls in libs/*.jar
RUN() { java "-Xmx${XMX}" -cp "$JAR" org.matsim.run.RunMatsim "$@"; }

# ---- 0. Java check (MATSim 2024.0: Java 17+) -------------------------------------------------------------------
JV="$(java -version 2>&1 | grep -m1 'version "' | sed -E 's/.*version "([0-9]+).*/\1/')"
[ "${JV:-0}" -ge 17 ] || { echo "need Java 17+, found '${JV:-none}'"; exit 1; }
[ "$MATSIM_VERSION" != "2026.0" ] || [ "$JV" -ge 21 ] || { echo "MATSim 2026.0 needs Java 21"; exit 1; }

# ---- 1. Download MATSim (about 100 MB; skipped if already unpacked) --------------------------------------------
mkdir -p "$WORK"
if [ ! -f "$JAR" ]; then
  curl -L --fail -C - -o "$WORK/matsim-${MATSIM_VERSION}-release.zip" "$ZIP_URL"
  # the 2024.0 zip measured 103,066,646 bytes, sha256 6d5d9cb81f3895209b101cdda30f40ac38a0557c1dd29c446e2748978f25200d
  [ "$MATSIM_VERSION" != "2024.0" ] || echo "6d5d9cb81f3895209b101cdda30f40ac38a0557c1dd29c446e2748978f25200d  $WORK/matsim-2024.0-release.zip" | sha256sum -c - || echo "WARNING: checksum differs from the one recorded when this runbook was written"
  unzip -q -o "$WORK/matsim-${MATSIM_VERSION}-release.zip" -d "$WORK"
fi

# ---- 2. Smoke test on MATSim's bundled 'equil' scenario: proves Java + MATSim run here (about a minute) --------
rm -rf "$WORK/equil" && cp -r "$WORK/matsim-${MATSIM_VERSION}/examples/equil" "$WORK/equil"
( cd "$WORK/equil" && RUN config.xml > smoke.log 2>&1 ) || { tail -30 "$WORK/equil/smoke.log"; exit 1; }
ls "$WORK/equil/output/output_plans.xml.gz" > /dev/null && echo "[smoke] equil OK (log: $WORK/equil/smoke.log)"

# ---- 3-5. Build, run and compare the town scenario, once per capacity factor ----------------------------------
for SHARE in $SHARES; do
  SC="$HERE/scenario/${TOWN}_share${SHARE}"
  mkdir -p "$SC"
  # 3a. towns.json -> network.xml (nodes/links in EPSG:32632, speeds by road class, both directions)
  python3 "$HERE/make_network.py" --town "$TOWN" --out "$SC/network.xml"
  # 3b. static benchmark's OD (seed 2026) -> plans.xml, home->work car trip, departures 07:00-09:00, plus scenario_meta.json
  python3 "$HERE/make_plans.py" --town "$TOWN" --agents "$AGENTS" --sample-share "$SHARE" --out "$SC/plans.xml"
  # 3c. standard config (qsim flow/storage capacity factor = SHARE)
  python3 "$HERE/make_config.py" --dir "$SC" --iterations "$ITERS" --sample-share "$SHARE"
  # 4. run MATSim (relative paths: run inside the scenario dir; output goes to $SC/output)
  ( cd "$SC" && RUN config.xml > matsim.log 2>&1 ) || { tail -30 "$SC/matsim.log"; exit 1; }
  # 5. compare: reads $SC/output/output_trips.csv.gz (or output_events.xml.gz); writes $SC/dynamic_crosscheck.json
  python3 "$HERE/compare_kpis.py" "$SC/output"
done
