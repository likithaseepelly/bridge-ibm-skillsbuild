"""Status and Loop agent.

Reads plan step status from the simulated pharmacy and scheduling feeds. It
never contacts the patient. When a feed is unavailable the step is marked
unknown, never complete.
"""

from typing import Any, Dict

AGENT = "status"


def check(record: Dict[str, Any], plan: Dict[str, Any], day: int,
          feed_available: bool = True) -> Dict[str, str]:
    """Simulated connector read. Returns the status of each plan step."""
    sim = record.get("_sim", {})
    out: Dict[str, str] = {}
    for step in plan["steps"]:
        sid = step["step_id"]
        if not feed_available:
            out[sid] = "unknown"
            continue
        if sid == "prescription_collected":
            d = sim.get("collects_prescription_day")
            out[sid] = _resolve(d, day, step["due_day"])
        elif sid == "appointment_booked":
            d = sim.get("books_appointment_day")
            out[sid] = _resolve(d, day, step["due_day"])
        elif sid == "appointment_attended":
            booked = sim.get("books_appointment_day")
            if booked is None:
                out[sid] = "failed" if day > step["due_day"] else "pending"
            else:
                attended_day = step["due_day"]
                out[sid] = _resolve(attended_day, day, step["due_day"])
        else:
            out[sid] = "pending"
    return out


def _resolve(event_day, today: int, due_day: int) -> str:
    if event_day is None:
        return "failed" if today > due_day else "pending"
    if today >= event_day:
        return "complete"
    return "pending"


def run(store, record: Dict[str, Any], plan: Dict[str, Any], day: int,
        feed_available: bool = True) -> Dict[str, Any]:
    statuses = check(record, plan, day, feed_available)
    changed = []
    for step in plan["steps"]:
        new = statuses[step["step_id"]]
        if new != step["status"]:
            changed.append((step["step_id"], step["status"], new))
            step["status"] = new
    if changed:
        store.put_plan(record["patient_id"], plan)
        store.audit(AGENT, "plan_status_changed", record["patient_id"],
                    day=day, changes=changed, feed_available=feed_available)
    return {"statuses": statuses, "changed": changed}
