"""Orchestrator.

Runs one daily cycle over the cohort: plan intake, outreach where due, inbound
replies, interpretation, status join, escalation check, then ranking.

On any agent failure the affected patient is raised to the nurse and the list
is marked degraded. Nothing is skipped silently.
"""

import copy
import random
from typing import Any, Dict, List, Optional

from . import config, synth
from .agents import escalation, interpretation, outreach, plan_intake, ranking, status
from .store import Store

AGENT = "orchestrator"


def bootstrap(store: Store, cohort: Optional[List[Dict[str, Any]]] = None) -> int:
    """Load the synthetic cohort and build a tracked plan for each patient."""
    cohort = cohort or synth.load_cohort()
    for record in cohort:
        store.put_patient(record)
        if not store.get_plan(record["patient_id"]):
            plan_intake.run(store, record)
    store.audit(AGENT, "bootstrap", None, patients=len(cohort))
    return len(cohort)


def _clarifications_sent(store: Store, patient_id: str) -> int:
    return sum(1 for m in store.messages_for(patient_id)
               if m["probing_step"] == "clarify")


def _due_for_outreach(store: Store, plan: Dict[str, Any], day: int) -> bool:
    sent_days = [m["day"] for m in store.messages_for(plan["patient_id"])
                 if m["probing_step"] != "emergency_guidance"]
    if not sent_days:
        return day >= 2
    cadence = 2 if plan.get("acuity") == "high" else 3
    return (day - max(sent_days)) >= cadence


def run_cycle(store: Store, day: int, rng: Optional[random.Random] = None,
              auto_approve: bool = True,
              fail_patients: Optional[set] = None) -> Dict[str, Any]:
    """One cycle. Returns a short summary for the caller."""
    rng = rng or random.Random(config.RANDOM_SEED + day)
    fail_patients = fail_patients or set()
    degraded: List[str] = []
    composed = approved = inbound = interpreted = 0
    cases: List[Dict[str, Any]] = []

    store.audit(AGENT, "cycle_started", None, day=day)

    for record in store.all_patients():
        pid = record["patient_id"]
        try:
            if pid in fail_patients:
                raise RuntimeError("injected agent failure")

            plan = store.get_plan(pid)
            if plan is None:
                plan = plan_intake.run(store, record)

            # 1. status join first, so outreach asks about the right step
            status.run(store, record, plan, day)

            # 2. outreach where due
            interps = store.interpretations_for(pid)
            needs_clarify = bool(interps) and interps[-1].get("ambiguity_flag") \
                and _clarifications_sent(store, pid) < config.MAX_CLARIFYING_QUESTIONS
            if _due_for_outreach(store, plan, day):
                msg = outreach.run(store, record, plan, day, needs_clarify)
                composed += 1
                if auto_approve and msg["status"] == "hold_for_approval":
                    store.approve_message(msg["message_id"], "simulated_nurse")
                    approved += 1

            # 3. inbound reply from the simulated messaging channel
            approved_today = [m for m in store.messages_for(pid)
                              if m["day"] == day and m["status"] in
                              ("approved", "ready")]
            if approved_today:
                reply = synth.simulated_reply(record, day, rng)
                if reply:
                    store.add_reply(pid, day, reply["author"], reply["text"])
                    inbound += 1

            # 4. interpretation of anything new
            for row in store.replies_for(pid):
                already = any(i["reply_id"] == row["reply_id"]
                              for i in store.interpretations_for(pid))
                if not already:
                    interpretation.run(store, row, plan)
                    interpreted += 1

            # 5. escalation, independent of ranking
            case = escalation.run(store, pid, day, plan,
                                  _clarifications_sent(store, pid))
            if case:
                cases.append(case)

        except Exception as exc:  # noqa: BLE001 - failures are raised, not hidden
            degraded.append(pid)
            store.audit(AGENT, "agent_failure", pid, day=day, error=str(exc))
            store.open_case(pid, day, "system_failure",
                            "Processing failed: %s" % exc,
                            "Review manually. The system could not assess this "
                            "patient this cycle.")

    rows = ranking.rank(store, day)
    if degraded:
        store.replace_ranking(day, rows, degraded=True)

    summary = {
        "day": day,
        "composed": composed,
        "approved": approved,
        "inbound_replies": inbound,
        "interpreted": interpreted,
        "cases_raised": len(cases),
        "ranked": len(rows),
        "degraded_patients": degraded,
        "top": [{"patient_id": r["patient_id"], "reason": r["reason"]}
                for r in rows[:config.WORKLIST_SIZE]],
    }
    store.audit(AGENT, "cycle_complete", None, **{
        k: v for k, v in summary.items() if k != "top"})
    return summary


def simulate(store: Store, days: int = 30, start_day: int = 1,
             fail_on_day: Optional[int] = None) -> List[Dict[str, Any]]:
    out = []
    for day in range(start_day, start_day + days):
        fail = set()
        if fail_on_day == day:
            pids = [p["patient_id"] for p in store.all_patients()][:2]
            fail = set(pids)
        out.append(run_cycle(store, day, fail_patients=fail))
    return out


# ---------------------------------------------------------------------------
# Dry-run helpers
# ---------------------------------------------------------------------------

def _row_counts(store: Store) -> Dict[str, int]:
    """Return current row counts for every mutable table.  Read-only."""
    tables = ["patients", "plans", "messages", "replies", "interpretations",
              "cases", "rankings", "nurse_actions", "audit"]
    counts: Dict[str, int] = {}
    for tbl in tables:
        rows = store.conn.execute("SELECT COUNT(*) AS n FROM %s" % tbl)
        counts[tbl] = rows[0]["n"]
    return counts


def build_cycle_plan(store: Store, day: int) -> List[Dict[str, Any]]:
    """Build and print the plan for *day* without writing anything to the DB.

    For each patient it describes what the live cycle would do and why:
    which outreach message would be composed, whether escalation would fire,
    and where the patient would land in the worklist — all from the current
    state of the database.  Nothing is written; no side effects.

    Returns a list of per-patient action dicts (one per patient).
    """
    patient_plans: List[Dict[str, Any]] = []

    print("=== Dry-run plan for day %d ===" % day)
    print("")

    # Pre-collect open cases once, mirroring ranking.rank.
    open_by_patient: Dict[str, Any] = {}
    for c in store.open_cases():
        open_by_patient.setdefault(c["patient_id"], dict(c))

    for record in store.all_patients():
        pid = record["patient_id"]
        entry: Dict[str, Any] = {
            "patient_id": pid,
            "name": record.get("name", pid),
            "outreach": None,
            "outreach_reason": None,
            "escalation": None,
            "ranking_score": None,
            "ranking_reason": None,
            "ranking_confidence": None,
            "ranking_evidence": [],
            "error": None,
        }

        try:
            plan = store.get_plan(pid)
            if plan is None:
                entry["error"] = "no plan — would run plan_intake"
                patient_plans.append(entry)
                print("  %s (%s): no plan on record, plan_intake would run"
                      % (record.get("name", pid), pid))
                continue

            # Work on a deep copy so the real plan is never mutated.
            plan_snapshot = copy.deepcopy(plan)

            # 1. Simulate status join — pure read; apply results to snapshot.
            status_result = status.check(record, plan_snapshot, day)
            for step in plan_snapshot["steps"]:
                step["status"] = status_result.get(step["step_id"], step["status"])

            # 2. Would outreach be due?
            if _due_for_outreach(store, plan_snapshot, day):
                interps = store.interpretations_for(pid)
                needs_clarify = (
                    bool(interps)
                    and interps[-1].get("ambiguity_flag")
                    and _clarifications_sent(store, pid) < config.MAX_CLARIFYING_QUESTIONS
                )
                msg = outreach.compose(record, plan_snapshot, day, needs_clarify)
                entry["outreach"] = msg["text"]
                entry["outreach_reason"] = msg["timing_reason"]
            else:
                entry["outreach_reason"] = "not due today"

            # 3. Would escalation fire?
            interps = store.interpretations_for(pid)
            replies = store.replies_for(pid)
            last_reply_day = replies[-1]["day"] if replies else None
            clarifications = _clarifications_sent(store, pid)
            esc_case = escalation.evaluate(pid, day, plan_snapshot, interps,
                                           last_reply_day, clarifications)
            # Suppress duplicates the same way run_cycle / escalation.run does.
            if esc_case:
                already_open = any(
                    c["patient_id"] == pid and c["trigger"] == esc_case["trigger"]
                    for c in store.open_cases()
                )
                if already_open:
                    esc_case = None
            entry["escalation"] = esc_case

            # 4. Ranking score — pure computation, no store writes.
            score, reason, conf, evidence = ranking.score_patient(
                plan_snapshot, interps, day, last_reply_day,
                open_by_patient.get(pid)
            )
            entry["ranking_score"] = round(score, 2)
            entry["ranking_reason"] = reason if reason else "(no score — would not appear)"
            entry["ranking_confidence"] = conf
            entry["ranking_evidence"] = evidence

        except Exception as exc:  # noqa: BLE001
            # Mirror run_cycle: a failing agent raises the patient; it is NOT
            # silently skipped.  In dry-run mode we record the error in the
            # entry so the caller can see which patient would be degraded.
            entry["error"] = "agent failure: %s" % exc

        patient_plans.append(entry)

        # ---- human-readable output ----------------------------------------
        print("  Patient: %s (%s)" % (entry["name"], pid))
        if entry["error"]:
            print("    ERROR (would be raised to nurse): %s" % entry["error"])
        else:
            if entry["outreach"]:
                print("    OUTREACH (%s):" % entry["outreach_reason"])
                print("      \"%s\"" % entry["outreach"])
            else:
                print("    outreach: %s" % entry["outreach_reason"])
            if entry["escalation"]:
                ec = entry["escalation"]
                print("    ESCALATE trigger=%s: %s" % (
                    ec["trigger"], ec["evidence"]))
            else:
                print("    escalation: none")
            print("    ranking  score=%.1f  %s" % (
                entry["ranking_score"] or 0.0,
                entry["ranking_reason"]))
        print("")

    print("=== end dry-run plan ===")
    return patient_plans
