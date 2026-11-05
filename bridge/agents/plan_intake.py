"""Plan Intake agent.

Turns one synthetic discharge record into a plan the system tracks. Every
warning sign carries the id of the passage it came from. The agent never states
a clinical instruction that is not in the record or in a retrieved passage.
"""

from typing import Any, Dict

from .. import config
from ..knowledge import index

AGENT = "plan_intake"


def build_plan(record: Dict[str, Any]) -> Dict[str, Any]:
    idx = index()
    signs = []
    for passage in idx.warning_signs(record["condition"]):
        signs.append({
            "text": passage["text"],
            "source_id": passage["id"],
            "emergency": "emergency sign" in passage["text"].lower(),
        })
    if not signs:
        raise ValueError("no grounded warning signs for %s" % record["condition"])

    steps = [
        {
            "step_id": "prescription_collected",
            "label": "New prescriptions collected",
            "due_day": config.PRESCRIPTION_DUE_DAY,
            "status": "pending",
        },
        {
            "step_id": "appointment_booked",
            "label": "Follow up appointment booked",
            "due_day": config.APPOINTMENT_BOOKED_DUE_DAY,
            "status": "pending",
        },
        {
            "step_id": "appointment_attended",
            "label": "Follow up appointment attended",
            "due_day": min(record.get("followup_day", 14),
                           config.APPOINTMENT_ATTENDED_DUE_DAY),
            "status": "pending",
        },
    ]

    # Higher acuity plans tolerate less silence before a human is pulled in.
    acuity = "high" if (record["lives_alone"] or record["condition"] == "heart_failure") \
        else "standard"
    silence_limit = 2 if acuity == "high" else config.SILENCE_LIMIT_DAYS

    return {
        "patient_id": record["patient_id"],
        "condition": record["condition"],
        "acuity": acuity,
        "silence_limit_days": silence_limit,
        "steps": steps,
        "warning_signs": signs,
        "built_by": AGENT,
    }


def run(store, record: Dict[str, Any]) -> Dict[str, Any]:
    plan = build_plan(record)
    store.put_plan(record["patient_id"], plan)
    store.audit(AGENT, "plan_created", record["patient_id"],
                steps=[s["step_id"] for s in plan["steps"]],
                warning_sign_sources=[s["source_id"] for s in plan["warning_signs"]],
                acuity=plan["acuity"])
    return plan
