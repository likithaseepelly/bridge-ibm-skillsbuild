"""Interpretation agent.

Reads a free text reply against the plan and the previous replies for that
patient. Two rules are absolute. An ambiguous reply is never resolved by
guessing, and any phrase suggesting an emergency sets concern to urgent.
"""

import re
from typing import Any, Dict, List, Optional

from .. import llm

AGENT = "interpretation"

URGENT_TERMS = [
    "chest pain", "chest pressure", "confused", "confusion", "not making sense",
    "blue", "grey lips", "unresponsive", "drowsy", "fainted", "passed out",
    "cannot breathe", "can not breathe", "cant breathe", "gasping",
    "coughing blood", "collapsed",
]
RISING_TERMS = [
    "more short of breath", "short of breath", "shortness of breath",
    "worse", "puffy", "swelling", "swollen", "sleep sitting up",
    "could not lie flat", "cannot lie flat", "weight is up", "scale is up",
    "pounds since", "green", "more of it", "shivery", "fever", "chills",
    "using the blue inhaler more", "more than usual", "tight",
]
REASSURING_TERMS = [
    "all good", "no problems", "about the same", "feeling fine", "doing ok",
    "doing okay", "no trouble", "has not changed", "nothing new", "fine thank",
]
AMBIGUOUS_WHOLE = {"ok", "okay", "k", "same", "fine", "yes", "no", "maybe",
                   "not sure", "not sure really", "cant say", "can not say",
                   "same i suppose", "dunno", "i suppose"}

STEP_DONE_TERMS = {
    "prescription_collected": ["picked up", "collected", "got the tablets",
                               "got the medicines", "have the tablets",
                               "picked them up"],
    "appointment_booked": ["appointment is booked", "booked for", "is booked",
                           "have an appointment", "appointment next"],
    "appointment_attended": ["went to the appointment", "saw the doctor",
                             "attended", "been to the clinic"],
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def _matched(terms: List[str], text: str) -> List[str]:
    return [t for t in terms if t in text]


def interpret(reply_text: str, plan: Dict[str, Any],
              history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    history = history or []
    text = _norm(reply_text)
    words = text.split()

    urgent_hits = _matched(URGENT_TERMS, text)
    rising_hits = _matched(RISING_TERMS, text)
    calm_hits = _matched(REASSURING_TERMS, text)

    ambiguity = False
    if text in AMBIGUOUS_WHOLE or (len(words) <= 4 and not urgent_hits
                                   and not rising_hits and not calm_hits):
        ambiguity = True

    if urgent_hits:
        concern, confidence = "urgent", 0.95
        phrases = urgent_hits
    elif ambiguity:
        # Do not guess. Ambiguity goes up, it does not get resolved here.
        concern, confidence = "unknown", 0.25
        phrases = [reply_text.strip()]
    elif rising_hits:
        prior = [h for h in history if h.get("concern_level") in ("rising", "mild")]
        concern = "rising"
        confidence = 0.8 if prior else 0.65
        phrases = rising_hits
    elif calm_hits:
        concern, confidence = "none", 0.7
        phrases = calm_hits
    else:
        concern, confidence = "mild", 0.45
        phrases = [reply_text.strip()[:120]]

    step_status = {}
    for step_id, terms in STEP_DONE_TERMS.items():
        if _matched(terms, text):
            step_status[step_id] = "complete"

    quote = " ".join(reply_text.strip().split())
    if len(quote) > 72:
        quote = quote[:69].rstrip(" ,.") + "..."

    result = {
        "quote": quote,
        "plan_step_status": step_status,
        "concern_level": concern,
        "ambiguity_flag": ambiguity,
        "confidence": confidence,
        "phrases": phrases,
        "engine": "rules",
        "agent": AGENT,
    }

    if llm.available() and concern != "urgent":
        enriched = _llm_second_opinion(reply_text, plan, result)
        if enriched:
            result.update(enriched)
    return result


def _llm_second_opinion(reply_text: str, plan: Dict[str, Any],
                        base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Granite is asked only to confirm or raise, never to lower a concern."""
    signs = "; ".join(s["text"] for s in plan["warning_signs"][:6])
    prompt = (
        "You read short messages from patients recovering at home after a "
        "hospital stay. Do not give advice. Do not diagnose.\n"
        "Condition warning signs: %s\n"
        "Message: %s\n"
        "Answer with one word only, from: none, mild, rising, urgent.\n"
        "Answer:" % (signs, reply_text)
    )
    out = llm.generate(prompt, max_tokens=5)
    if not out:
        return None
    word = out.strip().split()[0].lower().strip(".,")
    order = ["none", "mild", "rising", "urgent"]
    if word not in order:
        return None
    if base["concern_level"] == "unknown":
        return {"engine": "granite+rules"}
    if order.index(word) > order.index(base["concern_level"]):
        return {"concern_level": word, "engine": "granite+rules",
                "confidence": min(0.9, base["confidence"] + 0.1)}
    return {"engine": "granite+rules"}


def run(store, reply_row, plan: Dict[str, Any]) -> Dict[str, Any]:
    history = store.interpretations_for(reply_row["patient_id"])
    result = interpret(reply_row["text"], plan, history)
    iid = store.add_interpretation(reply_row["reply_id"], reply_row["patient_id"],
                                   reply_row["day"], result)
    result["interpretation_id"] = iid
    store.audit(AGENT, "reply_interpreted", reply_row["patient_id"],
                interpretation_id=iid, concern=result["concern_level"],
                ambiguous=result["ambiguity_flag"],
                confidence=result["confidence"], engine=result["engine"])
    return result
