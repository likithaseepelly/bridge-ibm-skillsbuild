"""One command demo.

    python3 run_demo.py            build cohort, run 12 cycles, start the worklist
    python3 run_demo.py --days 20  run more cycles first
    python3 run_demo.py --no-serve just run the cycles and print the summary
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
    args = ap.parse_args()

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
