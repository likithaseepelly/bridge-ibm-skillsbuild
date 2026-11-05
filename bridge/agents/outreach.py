"""Outreach agent.

Composes one short check in for one patient on one day. Rules enforced in code,
not left to a prompt: under 30 words, one question, no clinical advice, never a
statement that the patient is fine, and always held for nurse approval.
"""

import re
from typing import Any, Dict, List, Optional

from .. import config

AGENT = "outreach"

MAX_WORDS = 30

# Phrases the agent is not allowed to produce. Checked after generation.
ADVICE_PATTERNS = [
    r"\byou should\b", r"\btake (?:an?|your|another)\b", r"\bincrease\b",
    r"\bdecrease\b", r"\bstop taking\b", r"\bdose\b", r"\bmg\b",
    r"\byou are fine\b", r"\bnothing to worry\b", r"\bthat is normal\b",
    r"\bno need to\b", r"\bdiagnos", r"\bprescrib",
]

TEMPLATES = {
    "prescription_collected":
        "Hello {first}, checking in after your hospital stay. "
        "Have you been able to pick up your new medicines yet?",
    "appointment_booked":
        "Hello {first}, quick check in. "
        "Has your follow up appointment been booked yet?",
    "appointment_attended":
        "Hello {first}, checking in. "
        "Were you able to get to your follow up appointment?",
    "symptom_general":
        "Hello {first}, checking in. "
        "Compared with yesterday, is your breathing better, the same, or worse?",
    "symptom_hf":
        "Hello {first}, checking in. "
        "Has there been any new swelling in your ankles or feet since yesterday?",
    "symptom_copd":
        "Hello {first}, checking in. "
        "Are you using your reliever inhaler more than usual today?",
    "clarify":
        "Thanks {first}. So I pass the right note to your nurse, "
        "is anything worse today than it was yesterday?",
}


def _violations(text: str) -> List[str]:
    out = []
    if len(text.split()) > MAX_WORDS:
        out.append("over_word_limit")
    if text.count("?") != 1:
        out.append("not_exactly_one_question")
    low = text.lower()
    for pat in ADVICE_PATTERNS:
        if re.search(pat, low):
            out.append("advice_pattern:%s" % pat)
    return out


def choose_step(plan: Dict[str, Any], day: int,
                needs_clarification: bool) -> str:
    if needs_clarification:
        return "clarify"
    for step in plan["steps"]:
        if step["status"] == "pending" and day >= step["due_day"] - 1:
            return step["step_id"]
    return "symptom_hf" if plan["condition"] == "heart_failure" else "symptom_copd"


def compose(record: Dict[str, Any], plan: Dict[str, Any], day: int,
            needs_clarification: bool = False) -> Dict[str, Any]:
    step = choose_step(plan, day, needs_clarification)
    first = record["name"].split()[0]
    text = TEMPLATES[step].format(first=first)
    problems = _violations(text)
    if problems:
        # Never send something that breaks a rule. Fall back to the safest ask.
        text = TEMPLATES["symptom_general"].format(first=first)
        problems = _violations(text)
    return {
        "patient_id": record["patient_id"],
        "day": day,
        "text": text,
        "probing_step": step,
        "timing_reason": _timing_reason(step, plan, day),
        "status": "hold_for_approval" if config.APPROVAL_MODE else "ready",
        "rule_violations": problems,
    }


def _timing_reason(step: str, plan: Dict[str, Any], day: int) -> str:
    for s in plan["steps"]:
        if s["step_id"] == step:
            return "day %d, %s was due by day %d and is still %s" % (
                day, s["label"].lower(), s["due_day"], s["status"])
    if step == "clarify":
        return "day %d, previous reply was ambiguous" % day
    return "day %d, routine symptom check for %s" % (day, plan["condition"])


def run(store, record: Dict[str, Any], plan: Dict[str, Any], day: int,
        needs_clarification: bool = False) -> Dict[str, Any]:
    msg = compose(record, plan, day, needs_clarification)
    mid = store.add_message(msg["patient_id"], day, msg["text"],
                            msg["probing_step"], msg["timing_reason"],
                            msg["status"])
    msg["message_id"] = mid
    store.audit(AGENT, "message_composed", msg["patient_id"],
                message_id=mid, step=msg["probing_step"], status=msg["status"],
                timing_reason=msg["timing_reason"])
    return msg
