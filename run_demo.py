"""One command demo.

    py run_demo.py                  build cohort, run 12 cycles, start the worklist
    py run_demo.py --days 20        run more cycles first
    py run_demo.py --no-serve       just run the cycles and print the summary
    py run_demo.py --dry-run DAY    print what cycle DAY would do, write nothing
"""

import argparse
import os

from bridge import config, orchestrator, synth
from bridge.store import Store


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=12)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-serve", action="store_true")
    ap.add_argument("--keep", action="store_true",
                    help="keep the existing database instead of rebuilding")
    ap.add_argument("--dry-run", type=int, metavar="DAY", dest="dry_run",
                    help="print the plan for DAY without writing to the database")
    args = ap.parse_args()

    # --dry-run: load (or build) state, print the plan, exit — no DB writes.
    if args.dry_run is not None:
        if not config.DB_PATH.exists():
            # No existing database; build one so there is state to inspect.
            if not args.keep:
                info = synth.write_cohort()
                print("Cohort: %d synthetic patients, %d with scripted deterioration"
                      % (info["count"], info["seeded"]))
            store = Store()
            orchestrator.bootstrap(store)
            orchestrator.simulate(store, days=args.dry_run - 1)
        else:
            store = Store()
        orchestrator.build_cycle_plan(store, args.dry_run)
        store.close()
        return

    if not args.keep and config.DB_PATH.exists():
        os.remove(config.DB_PATH)

    info = synth.write_cohort()
    print("Cohort: %d synthetic patients, %d with scripted deterioration"
          % (info["count"], info["seeded"]))
    print("Ground truth held in %s and never read by any agent" % info["truth_path"])

    store = Store()
    orchestrator.bootstrap(store)
    summaries = orchestrator.simulate(store, days=args.days, fail_on_day=9)

    last = summaries[-1]
    print("")
    print("Ran %d cycles. Day %d summary:" % (len(summaries), last["day"]))
    print("  messages composed      %d" % last["composed"])
    print("  replies received       %d" % last["inbound_replies"])
    print("  replies interpreted    %d" % last["interpreted"])
    print("  cases raised today     %d" % last["cases_raised"])
    print("  patients ranked        %d" % last["ranked"])
    if last["degraded_patients"]:
        print("  degraded (raised, not skipped) %s" % last["degraded_patients"])
    print("")
    print("Top of the nurse worklist:")
    for i, row in enumerate(last["top"], start=1):
        rec = store.get_patient(row["patient_id"])
        print("  %d. %-22s %s" % (i, rec["name"], row["reason"]))
    store.close()

    if not args.no_serve:
        from bridge import server
        print("")
        server.serve(port=args.port)


if __name__ == "__main__":
    main()
