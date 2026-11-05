"""Triage and Ranking agent.

Orders the cohort every cycle on change against the patient's own baseline, not
against the population. Every entry carries a one sentence reason and the
evidence ids behind it. If a reason cannot be written in one sentence the
patient is marked as insufficient evidence and raised rather than ranked.
No output ever means the patient is safe.
"""

from typing import Any, Dict, List, Optional, Tuple

AGENT = "ranking"

CONCERN_WEIGHT = {"urgent": 100.0, "rising": 40.0, "mild": 8.0,
                  "unknown": 18.0, "none": 0.0}


def _trend(interps: List[Dict[str, Any]]) -> float:
    """Movement against this patient's own baseline, not the cohort."""
    if len(interps) < 2:
        return 0.0
    order = ["none", "mild", "unknown", "rising", "urgent"]
    prev = order.index(interps[-2].get("concern_level", "none"))
    curr = order.index(interps[-1].get("concern_level", "none"))
    return float(curr - prev) * 12.0


def _recency(day: int, event_day: Optional[int]) -> float:
    """New evidence outranks old evidence the nurse has already been shown."""
    if event_day is None:
        return 0.5
    age = day - event_day
    if age <= 1:
        return 1.0
    if age <= 3:
        return 0.75
    if age <= 6:
        return 0.5
    return 0.35


SILENCE_CAP = 30.0
FAILED_STEP_CAP = 24.0


def score_patient(plan: Dict[str, Any], interps: List[Dict[str, Any]],
                  day: int, last_reply_day: Optional[int],
                  open_case: Optional[Dict[str, Any]]) -> Tuple[float, str, float, List[str]]:
    latest = interps[-1] if interps else None
    evidence: List[str] = []
    score = 0.0
    parts: List[str] = []

    if latest:
        level = latest.get("concern_level", "none")
        recency = _recency(day, latest.get("day"))
        score += CONCERN_WEIGHT.get(level, 0.0) * recency
        evidence.append("interpretation:%s" % latest.get("interpretation_id"))
        if level == "urgent":
            quote = (latest.get("quote") or "an emergency sign").rstrip(".")
            parts.append("reported an emergency sign, %s" % quote)
        elif level == "rising":
            quote = (latest.get("quote") or "worse than before").rstrip(".")
            parts.append("said %s" % quote)
        elif level == "unknown":
            parts.append("sent a reply that could not be interpreted")

        trend = _trend(interps) * recency
        score += trend
        if len(interps) >= 2 and trend > 0:
            parts.append("worse than their own previous reply")

    silent_for = day if last_reply_day is None else day - last_reply_day
    limit = plan.get("silence_limit_days", 3)
    if silent_for > limit:
        silence_score = min(SILENCE_CAP, 15.0 + 4.0 * (silent_for - limit))
        # Once silence has already been raised to the nurse it stops climbing.
        if open_case and open_case.get("trigger") == "extended_silence" \
                and day - open_case.get("day", day) > 2:
            silence_score *= 0.5
        score += silence_score
        parts.append("no reply for %d days" % silent_for)
        evidence.append("silence:%d" % silent_for)

    failed = [s for s in plan["steps"] if s["status"] == "failed"]
    if failed:
        step_score = min(FAILED_STEP_CAP, 12.0 * len(failed))
        if open_case and open_case.get("trigger") == "plan_step_failed" \
                and day - open_case.get("day", day) > 2:
            step_score *= 0.5
        score += step_score
        parts.append("%s overdue" % failed[0]["label"].lower())
        evidence.extend("step:%s" % s["step_id"] for s in failed)

    if plan.get("acuity") == "high":
        score *= 1.15

    if open_case:
        age = day - open_case.get("day", day)
        score += 25.0 if age <= 1 else 8.0
        evidence.append("case:%s" % open_case["case_id"])

    if not parts:
        return score, "", 0.0, evidence

    joined = "; ".join(parts[:2])
    reason = joined[0].upper() + joined[1:] + "."
    confidence = latest.get("confidence", 0.4) if latest else 0.3
    if silent_for > limit:
        confidence = max(confidence, 0.6)
    return score, reason, round(confidence, 2), evidence


def rank(store, day: int) -> List[Dict[str, Any]]:
    scored = []
    insufficient = []
    open_by_patient = {}
    for c in store.open_cases():
        open_by_patient.setdefault(c["patient_id"], dict(c))

    for record in store.all_patients():
        pid = record["patient_id"]
        plan = store.get_plan(pid)
        if not plan:
            continue
        interps = store.interpretations_for(pid)
        replies = store.replies_for(pid)
        last_reply_day = replies[-1]["day"] if replies else None
        score, reason, conf, evidence = score_patient(
            plan, interps, day, last_reply_day, open_by_patient.get(pid))

        if score <= 0:
            continue
        if not reason:
            insufficient.append(pid)
            continue
        scored.append({
            "patient_id": pid, "score": score, "reason": reason,
            "confidence": conf, "evidence_ids": evidence,
        })

    scored.sort(key=lambda r: r["score"], reverse=True)
    for i, row in enumerate(scored, start=1):
        row["position"] = i

    store.replace_ranking(day, scored)
    store.audit(AGENT, "cohort_ranked", None, cycle_day=day,
                ranked=len(scored), insufficient_evidence=insufficient)
    return scored
