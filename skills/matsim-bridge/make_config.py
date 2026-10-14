#!/usr/bin/env python3
"""Write a minimal, standard MATSim config.xml for a scenario made by make_network.py / make_plans.py.

    python make_config.py --dir scenario/molde --iterations 20 --sample-share 0.1

Module names follow MATSim 2024.0 (controller / scoring / replanning), checked against the release's own
examples/scenarios/equil/config.xml. Every non-default choice is listed here:

  global.coordinateSystem      EPSG:32632 (the frame of towns.json); global.randomSeed 2026; 1 thread (reproducible)
  controller.lastIteration     --iterations (default 20); writeEventsInterval = lastIteration, so output_events.xml.gz
                               holds the FINAL iteration; output_trips.csv.gz is always written at the end
  qsim.flowCapacityFactor      --sample-share. 1.0 = the agents are the whole peak population (little congestion at
  qsim.storageCapacityFactor   1,000 agents on a town network); 0.1 = each agent stands for ten commuters, i.e. 1,000
                               agents load the network like 10,000. This is an ASSUMPTION, not calibrated to counts.
  qsim.stuckTime               3600 s (default 10 s would silently delete agents in a jam; we want to see them)
  qsim.endTime                 00:00:00 = run until every agent has arrived
  scoring                      standard Charypar-Nagel utilities: car -6 /h travelling, performing +6 /h, home typical
                               12 h, work typical 8 h; no opening times (the plans contain a single morning trip)
  replanning                   ChangeExpBeta 0.8 + ReRoute 0.2, innovation switched off after 80 % of iterations;
                               no time or mode mutation: departure times and car mode are the demand, only routes adapt
"""
import argparse
import json
from pathlib import Path

CONFIG = """<?xml version="1.0" ?>
<!DOCTYPE config SYSTEM "http://www.matsim.org/files/dtd/config_v2.dtd">
<config>
	<module name="global">
		<param name="randomSeed" value="2026" />
		<param name="coordinateSystem" value="{crs}" />
		<param name="numberOfThreads" value="1" />
	</module>

	<module name="network">
		<param name="inputNetworkFile" value="network.xml" />
	</module>

	<module name="plans">
		<param name="inputPlansFile" value="plans.xml" />
	</module>

	<module name="controller">
		<param name="outputDirectory" value="./output" />
		<param name="overwriteFiles" value="deleteDirectoryIfExists" />
		<param name="firstIteration" value="0" />
		<param name="lastIteration" value="{iters}" />
		<param name="writeEventsInterval" value="{iters}" />
		<param name="writePlansInterval" value="{iters}" />
		<param name="writeTripsInterval" value="{iters}" />
		<param name="mobsim" value="qsim" />
	</module>

	<module name="qsim">
		<param name="startTime" value="00:00:00" />
		<param name="endTime" value="00:00:00" />
		<param name="flowCapacityFactor" value="{share}" />
		<param name="storageCapacityFactor" value="{share}" />
		<param name="stuckTime" value="3600" />
		<param name="numberOfThreads" value="1" />
		<param name="mainMode" value="car" />
	</module>

	<module name="routing">
		<param name="networkModes" value="car" />
	</module>

	<module name="scoring">
		<param name="learningRate" value="1.0" />
		<param name="brainExpBeta" value="1.0" />
		<parameterset type="scoringParameters">
			<param name="lateArrival" value="-18" />
			<param name="earlyDeparture" value="-0" />
			<param name="performing" value="+6" />
			<param name="waiting" value="-0" />
			<parameterset type="modeParams">
				<param name="mode" value="car" />
				<param name="marginalUtilityOfTraveling_util_hr" value="-6.0" />
			</parameterset>
			<parameterset type="activityParams">
				<param name="activityType" value="home" />
				<param name="typicalDuration" value="12:00:00" />
			</parameterset>
			<parameterset type="activityParams">
				<param name="activityType" value="work" />
				<param name="typicalDuration" value="08:00:00" />
			</parameterset>
		</parameterset>
	</module>

	<module name="replanning">
		<param name="maxAgentPlanMemorySize" value="5" />
		<param name="fractionOfIterationsToDisableInnovation" value="0.8" />
		<parameterset type="strategysettings">
			<param name="strategyName" value="ChangeExpBeta" />
			<param name="weight" value="0.8" />
		</parameterset>
		<parameterset type="strategysettings">
			<param name="strategyName" value="ReRoute" />
			<param name="weight" value="0.2" />
		</parameterset>
	</module>
</config>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, required=True, help="scenario directory holding network.xml and plans.xml")
    ap.add_argument("--iterations", type=int, default=20)
    ap.add_argument("--sample-share", type=float, default=1.0, help="flow/storage capacity factor, (0, 1]")
    a = ap.parse_args()
    if not 0 < a.sample_share <= 1:
        raise SystemExit("--sample-share must be in (0, 1]")
    for f in ("network.xml", "plans.xml"):
        if not (a.dir / f).exists():
            raise SystemExit(f"{a.dir / f} missing: run make_network.py and make_plans.py first")
    (a.dir / "config.xml").write_text(CONFIG.format(crs="EPSG:32632", iters=a.iterations, share=a.sample_share))
    mf = a.dir / "scenario_meta.json"
    if mf.exists():                                   # let compare_kpis.py label the run correctly
        m = json.loads(mf.read_text())
        m.update(sample_share=a.sample_share, iterations=a.iterations)
        mf.write_text(json.dumps(m))
    print(f"config.xml: {a.iterations} iterations, flow/storage capacity factor {a.sample_share} -> {a.dir / 'config.xml'}")


if __name__ == "__main__":
    main()
