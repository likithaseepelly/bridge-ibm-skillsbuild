"""Evaluation harness.

Replays 30 simulated days against a seeded synthetic cohort and reports the
five numbers that tell you whether the system works:

  detection rate, cycles to detection, noise in the top five,
  deferred urgent replies, and reason coverage.

Ground truth lives in eval/ground_truth.json and is never read by any agent.
"""

import json
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bridge import config, llm, orchestrator, synth  # noqa: E402
from bridge.store import Store  # noqa: E402

DAYS = 30
DB = config.OUT_DIR / "eval.db"


def build_store(fresh: bool = True) -> Store:
    if fresh and DB.exists():
        os.remove(DB)
    return Store(DB)


def run(days: int = DAYS, fail_on_day: int = 12, cohort_size: int = None,
        seeded: int = None) -> dict:
    synth.write_cohort(size=cohort_size, seeded=seeded)
    store = build_store()
    orchestrator.bootstrap(store)
    orchestrator.simulate(store, days=days, fail_on_day=fail_on_day)

    truth = synth.load_ground_truth()["events"]
    seeded = set(truth)

    # ---- detection and latency ------------------------------------------
    detected, latencies, missed = {}, [], []
    for pid, event in truth.items():
        onset = event["first_signal_day"]
        found_day = None
        for day in range(onset, days + 1):
            top = store.ranking(day)[:config.WORKLIST_SIZE]
            if any(r["patient_id"] == pid for r in top):
                found_day = day
                break
        if found_day is None:
            missed.append(pid)
        else:
            detected[pid] = found_day
            latencies.append(found_day - onset)

    # ---- what is filling the top five ------------------------------------
    # A top five slot is only a false positive if nothing real put it there.
    # A missed prescription or a patient who has gone quiet is a genuine
    # reason to call, even though the ground truth does not score it.
    top_slots = 0
    noise_slots = 0
    seeded_slots = 0
    other_adverse_slots = 0
    unexplained_slots = 0
    for day in range(1, days + 1):
        for row in store.ranking(day)[:config.WORKLIST_SIZE]:
            top_slots += 1
            if row["patient_id"] in seeded:
                seeded_slots += 1
                continue
            noise_slots += 1
            ev = " ".join(row["evidence_ids"])
            if "step:" in ev or "silence:" in ev or "case:" in ev:
                other_adverse_slots += 1
            else:
                unexplained_slots += 1

    # ---- deferred urgent replies (must be zero) --------------------------
    deferred = []
    for record in store.all_patients():
        pid = record["patient_id"]
        case_days = [c["day"] for c in store.cases_for(pid)
                     if c["trigger"] == "urgent_reply"]
        for interp in store.interpretations_for(pid):
            if interp.get("concern_level") == "urgent":
                if not any(d <= interp["day"] for d in case_days):
                    deferred.append({"patient_id": pid, "day": interp["day"]})

    # ---- reason coverage --------------------------------------------------
    checked = empty_reason = no_evidence = 0
    for day in range(1, days + 1):
        for row in store.ranking(day):
            checked += 1
            if not row["reason"].strip():
                empty_reason += 1
            if not row["evidence_ids"]:
                no_evidence += 1

    # ---- degraded handling ------------------------------------------------
    failure_cases = [dict(c) for c in store.open_cases()
                     if c["trigger"] == "system_failure"]

    # Which brain actually read the replies. Recorded so a run can never be
    # mistaken for a watsonx run when it quietly fell back to the rules.
    engines = set()
    for record in store.all_patients():
        for interp in store.interpretations_for(record["patient_id"]):
            engines.add(interp.get("engine", "rules"))

    results = {
        "interpretation_engines_observed": sorted(engines),
        "watsonx_configured": config.watsonx_configured(),
        "watsonx_model_id": (config.WATSONX_MODEL_ID
                             if config.watsonx_configured() else None),
        "watsonx_calls": dict(llm.CALLS),
        "cohort_size": len(store.all_patients()),
        "seeded_events": len(truth),
        "days_simulated": days,
        "detection_rate": round(len(detected) / max(1, len(truth)), 3),
        "detected": len(detected),
        "missed": missed,
        "median_cycles_to_detection": (
            statistics.median(latencies) if latencies else None),
        "max_cycles_to_detection": max(latencies) if latencies else None,
        "top_five_slots": top_slots,
        "seeded_slots": seeded_slots,
        "other_adverse_slots": other_adverse_slots,
        "unexplained_slots": unexplained_slots,
        "noise_slots": noise_slots,
        "noise_rate": round(noise_slots / max(1, top_slots), 3),
        "unexplained_rate": round(unexplained_slots / max(1, top_slots), 3),
        "deferred_urgent_replies": len(deferred),
        "deferred_detail": deferred,
        "ranked_entries_checked": checked,
        "entries_without_reason": empty_reason,
        "entries_without_evidence": no_evidence,
        "injected_failures_surfaced": len(failure_cases),
        "total_cases_opened": len(store.open_cases()),
    }

    tag = "granite" if "granite+rules" in results[
        "interpretation_engines_observed"] else "rules"
    results["run_tag"] = tag
    (config.OUT_DIR / "eval_results.json").write_text(
        json.dumps(results, indent=2))
    (config.OUT_DIR / ("eval_results_%s.json" % tag)).write_text(
        json.dumps(results, indent=2))
    store.close()
    return results


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Bridge evaluation harness")
    ap.add_argument("--days", type=int, default=DAYS)
    ap.add_argument("--cohort", type=int, default=None,
                    help="cohort size, default %d" % config.COHORT_SIZE)
    ap.add_argument("--seeded", type=int, default=None,
                    help="scripted deterioration events, default %d"
                         % config.SEEDED_DETERIORATION)
    args = ap.parse_args()

    if config.watsonx_configured():
        print("watsonx.ai is configured. Every reply will be sent to %s for a"
              % config.WATSONX_MODEL_ID)
        print("second opinion, so this run will be slower than the rule engine.")
    else:
        print("watsonx.ai is not configured. Running on the rule engine.")

    r = run(days=args.days, cohort_size=args.cohort, seeded=args.seeded)
    print("")
    print("Bridge evaluation, %d synthetic patients, %d simulated days"
          % (r["cohort_size"], r["days_simulated"]))
    print("Interpretation engine          %s"
          % ", ".join(r["interpretation_engines_observed"]))
    print("-" * 62)
    print("Detection rate                  %.0f%% (%d of %d seeded events)"
          % (r["detection_rate"] * 100, r["detected"], r["seeded_events"]))
    print("Median cycles to detection      %s" % r["median_cycles_to_detection"])
    print("Worst case cycles to detection  %s" % r["max_cycles_to_detection"])
    print("Top five slots, %d in total" % r["top_five_slots"])
    print("  seeded deterioration          %d" % r["seeded_slots"])
    print("  other real reason to call     %d  (overdue step, silence, open case)"
          % r["other_adverse_slots"])
    print("  unexplained                   %d  (%.0f%%, the true false positives)"
          % (r["unexplained_slots"], r["unexplained_rate"] * 100))
    print("Deferred urgent replies         %d   (target 0)"
          % r["deferred_urgent_replies"])
    print("Ranked entries with no reason   %d of %d"
          % (r["entries_without_reason"], r["ranked_entries_checked"]))
    print("Ranked entries with no evidence %d of %d"
          % (r["entries_without_evidence"], r["ranked_entries_checked"]))
    print("Injected failures surfaced      %d   (raised, not skipped)"
          % r["injected_failures_surfaced"])
    print("-" * 62)
    calls = r.get("watsonx_calls") or {}
    if calls.get("attempted"):
        print("watsonx.ai calls                %d attempted, %d answered, "
              "%d fell back to rules"
              % (calls["attempted"], calls["succeeded"], calls["failed"]))
        if calls.get("last_error"):
            print("  last error                    %s" % calls["last_error"])
    print("Run tag                         %s" % r["run_tag"])
    print("Written to %s" % (config.OUT_DIR / "eval_results.json"))
    print("     and to %s"
          % (config.OUT_DIR / ("eval_results_%s.json" % r["run_tag"])))
    return 0 if r["deferred_urgent_replies"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
