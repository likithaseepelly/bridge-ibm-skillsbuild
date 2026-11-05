"""Orchestrator.

Runs one daily cycle over the cohort: plan intake, outreach where due, inbound
replies, interpretation, status join, escalation check, then ranking.

On any agent failure the affected patient is raised to the nurse and the list
is marked degraded. Nothing is skipped silently.
"""

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
