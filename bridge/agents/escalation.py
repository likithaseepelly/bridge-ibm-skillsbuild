"""Escalation and Safety agent.

Runs independently of the ranking. It raises a case immediately on an urgent
reply, when ambiguity persists after one clarifying question, and when a
patient has been silent for longer than their plan allows. It never closes a
case and it never suppresses an escalation to keep the list short.
"""

from typing import Any, Dict, List, Optional

from .. import config

AGENT = "escalation"

EMERGENCY_GUIDANCE = (
    "If this is an emergency, call 911 or go to the nearest emergency "
    "department now. A nurse has been alerted to this message."
)


def evaluate(patient_id: str, day: int, plan: Dict[str, Any],
             interpretations: List[Dict[str, Any]],
             last_reply_day: Optional[int],
             clarifications_sent: int) -> Optional[Dict[str, Any]]:
    """Return a case to raise, or None. Order matters: urgent first."""
    latest = interpretations[-1] if interpretations else None

    if latest and latest.get("concern_level") == "urgent":
        return {
            "trigger": "urgent_reply",
            "evidence": "Reply on day %d: %s" % (
                latest.get("day", day), "; ".join(latest.get("phrases", []))),
            "recommended_action":
                "Call now. Emergency guidance was shown to the sender.",
            "show_emergency_guidance": True,
            "priority": 0,
        }

    if latest and latest.get("ambiguity_flag") and clarifications_sent >= \
            config.MAX_CLARIFYING_QUESTIONS:
        return {
            "trigger": "persistent_ambiguity",
            "evidence": "Reply on day %d could not be interpreted after %d "
                        "clarifying question: %s" % (
                            latest.get("day", day), clarifications_sent,
                            "; ".join(latest.get("phrases", []))),
            "recommended_action": "Call to establish how the patient is doing.",
            "show_emergency_guidance": False,
            "priority": 1,
        }

    limit = plan.get("silence_limit_days", config.SILENCE_LIMIT_DAYS)
    if last_reply_day is None:
        silent_for = day
    else:
        silent_for = day - last_reply_day
    if silent_for > limit:
        return {
            "trigger": "extended_silence",
            "evidence": "No reply for %d days, plan allows %d (acuity %s)" % (
                silent_for, limit, plan.get("acuity", "standard")),
            "recommended_action":
                "Call. Silence is not reassurance and this plan is %s acuity."
                % plan.get("acuity", "standard"),
            "show_emergency_guidance": False,
            "priority": 2,
        }

    failed = [s for s in plan["steps"] if s["status"] == "failed"]
    if failed:
        return {
            "trigger": "plan_step_failed",
            "evidence": "Overdue: %s" % ", ".join(s["label"] for s in failed),
            "recommended_action": "Call to find out what is blocking this step.",
            "show_emergency_guidance": False,
            "priority": 3,
        }
    return None


def run(store, patient_id: str, day: int, plan: Dict[str, Any],
        clarifications_sent: int) -> Optional[Dict[str, Any]]:
    interps = store.interpretations_for(patient_id)
    replies = store.replies_for(patient_id)
    last_reply_day = replies[-1]["day"] if replies else None

    case = evaluate(patient_id, day, plan, interps, last_reply_day,
                    clarifications_sent)
    if not case:
        return None

    # Do not raise the same trigger twice while it is still open.
    for existing in store.open_cases():
        if existing["patient_id"] == patient_id and \
                existing["trigger"] == case["trigger"]:
            return None

    case_id = store.open_case(patient_id, day, case["trigger"],
                              case["evidence"], case["recommended_action"])
    case["case_id"] = case_id
    store.audit(AGENT, "case_raised", patient_id, case_id=case_id,
                trigger=case["trigger"], day=day,
                emergency_guidance=case["show_emergency_guidance"])
    if case["show_emergency_guidance"]:
        store.add_message(patient_id, day, EMERGENCY_GUIDANCE,
                          "emergency_guidance", "urgent reply received",
                          "sent_immediately")
        store.audit(AGENT, "emergency_guidance_shown", patient_id, day=day)
    return case
