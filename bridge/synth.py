"""Synthetic cohort generator.

No real data is used at any point. Names are drawn from a fixed invented list.
Deterioration is scripted into a known subset and the ground truth is written to
eval/ground_truth.json, which the agents never read.
"""

import json
import random
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from . import config

FIRST_NAMES = [
    "Rosa", "Darnell", "Mei", "Terrence", "Ingrid", "Salvatore", "Nadia",
    "Leonard", "Priya", "Marcus", "Delphine", "Osman", "Yvette", "Clifford",
    "Ana", "Boris", "Georgia", "Hassan", "Ivy", "Joachim", "Karla", "Linus",
    "Marisol", "Nkechi", "Otto", "Paloma", "Quentin", "Rhoda", "Stefan",
    "Tamsin", "Ulrich", "Valeria", "Wendell", "Xiomara", "Yusuf", "Zelda",
]
LAST_NAMES = [
    "Okafor", "Delgado", "Whitlock", "Bergstrom", "Nakamura", "Ferreira",
    "Haddad", "Kowalski", "Ananthan", "Brennan", "Castellanos", "Dufresne",
    "Eriksen", "Fontaine", "Gallagher", "Hollins", "Iyengar", "Jarvis",
    "Kirkpatrick", "Lindqvist", "Mbeki", "Novotny", "Oyelaran", "Pembroke",
]

HF_MEDS = [
    ("Furosemide 40 mg", "once each morning"),
    ("Lisinopril 10 mg", "once each morning"),
    ("Carvedilol 6.25 mg", "twice a day with food"),
    ("Spironolactone 25 mg", "once each morning"),
    ("Potassium chloride 20 mEq", "once a day"),
]
COPD_MEDS = [
    ("Prednisone 40 mg", "once a day for five days"),
    ("Azithromycin 250 mg", "once a day for five days"),
    ("Tiotropium inhaler", "one puff each morning"),
    ("Albuterol inhaler", "as needed for breathlessness"),
    ("Doxycycline 100 mg", "twice a day for seven days"),
]
T2D_MEDS = [
    ("Metformin 500 mg", "twice a day with meals"),
    ("Empagliflozin 10 mg", "once each morning"),
    ("Insulin glargine 10 units", "once at bedtime"),
    ("Gliclazide 40 mg", "once each morning with breakfast"),
    ("Sitagliptin 100 mg", "once each morning"),
]

# Reply text by trajectory. Written as a patient or relative would text.
STABLE_REPLIES = [
    "All good here thanks. Picked up the tablets yesterday.",
    "Feeling about the same as when I left. No problems.",
    "Bit tired but nothing new. Appointment is booked for next week.",
    "Doing ok. Weight has not changed.",
    "Fine thank you. Walking to the kitchen and back with no trouble.",
]
AMBIGUOUS_REPLIES = [
    "ok",
    "mum says she is managing",
    "not sure really",
    "same i suppose",
    "cant say",
]
HF_DECLINE = [
    "Bit more puffy round the ankles today than yesterday.",
    "Scale is up four pounds since Monday and the shoes are tight.",
    "Had to sleep sitting up last night, could not lie flat.",
    "Short of breath just getting to the bathroom now. Worse than yesterday.",
]
COPD_DECLINE = [
    "Using the blue inhaler more than usual the last two days.",
    "Phlegm has gone green and there is more of it.",
    "More out of breath getting dressed than I was last week.",
    "Been shivery and the cough is different now.",
]
T2D_DECLINE = [
    "Blood sugar readings have been very high the last two days.",
    "Feeling much more thirsty than usual and going to the toilet a lot.",
    "Foot is red and swollen where the sore is, does not look right.",
    "Feeling sick and stomach hurts, sugar was very high this morning.",
]
URGENT_REPLIES = [
    "He is confused this morning and not making sense, I am worried.",
    "I have chest pain and it is not going away.",
    "His lips look blue and he is very drowsy.",
]


def _rng(seed: Optional[int] = None) -> random.Random:
    return random.Random(config.RANDOM_SEED if seed is None else seed)


def generate_cohort(size: int = None, seeded: int = None,
                    seed: int = None) -> Dict[str, Any]:
    """Build the cohort and the hidden ground truth in one pass."""
    size = size or config.COHORT_SIZE
    seeded = seeded if seeded is not None else config.SEEDED_DETERIORATION
    rng = _rng(seed)
    day_zero = date(2026, 11, 1)

    indices = list(range(size))
    rng.shuffle(indices)
    deteriorating = set(indices[:seeded])
    # A quarter of the remainder never reply at all. Silence is a signal, not
    # reassurance, so the system has to handle them rather than ignore them.
    silent = set(indices[seeded:seeded + max(1, (size - seeded) // 8)])

    patients: List[Dict[str, Any]] = []
    truth: Dict[str, Any] = {"generated_with_seed": seed or config.RANDOM_SEED,
                             "events": {}}

    used_names = set()
    for i in range(size):
        while True:
            name = "%s %s" % (rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES))
            if name not in used_names:
                used_names.add(name)
                break
        condition = rng.choice(config.CONDITIONS)
        if condition == "heart_failure":
            meds_pool = HF_MEDS
        elif condition == "copd":
            meds_pool = COPD_MEDS
        else:
            meds_pool = T2D_MEDS
        meds = rng.sample(meds_pool, rng.randint(3, min(5, len(meds_pool))))
        discharge_offset = rng.randint(0, 3)
        pid = "P%03d" % (i + 1)

        if i in deteriorating:
            trajectory = "deteriorating"
            onset_day = rng.randint(3, 11)
            urgent = rng.random() < 0.34
            truth["events"][pid] = {
                "trajectory": trajectory,
                "first_signal_day": onset_day,
                "becomes_urgent": urgent,
                "urgent_day": onset_day + 3 if urgent else None,
            }
        elif i in silent:
            trajectory = "silent"
            onset_day = None
            urgent = False
        else:
            trajectory = "stable"
            onset_day = None
            urgent = False

        patients.append({
            "patient_id": pid,
            "name": name,
            "condition": condition,
            "discharge_date": (day_zero + timedelta(days=discharge_offset)).isoformat(),
            "age_band": rng.choice(["55 to 64", "65 to 74", "75 to 84", "85 plus"]),
            "lives_alone": rng.random() < 0.35,
            "caregiver_contact": rng.random() < 0.55,
            "medications": [{"name": n, "schedule": s} for n, s in meds],
            "followup_day": rng.choice([7, 10, 12, 14]),
            # Simulation only. The agents never read these three fields.
            "_sim": {
                "trajectory": trajectory,
                "onset_day": onset_day,
                "urgent": urgent,
                "collects_prescription_day": (
                    None if rng.random() < 0.18 else rng.randint(1, 4)),
                "books_appointment_day": (
                    None if rng.random() < 0.22 else rng.randint(2, 9)),
                "reply_rate": round(rng.uniform(0.55, 0.95), 2),
            },
        })

    return {"patients": patients, "ground_truth": truth}


def simulated_reply(patient: Dict[str, Any], day: int,
                    rng: random.Random) -> Optional[Dict[str, str]]:
    """What this patient would send back on this day, if anything."""
    sim = patient["_sim"]
    if sim["trajectory"] == "silent":
        return None
    if rng.random() > sim["reply_rate"]:
        return None

    author = "caregiver" if patient["caregiver_contact"] and rng.random() < 0.3 \
        else "patient"

    if sim["trajectory"] == "deteriorating" and day >= (sim["onset_day"] or 99):
        if sim["urgent"] and day >= sim["onset_day"] + 3:
            return {"author": "caregiver", "text": rng.choice(URGENT_REPLIES)}
        if patient["condition"] == "heart_failure":
            pool = HF_DECLINE
        elif patient["condition"] == "copd":
            pool = COPD_DECLINE
        else:
            pool = T2D_DECLINE
        step = min(day - sim["onset_day"], len(pool) - 1)
        return {"author": author, "text": pool[step]}

    if rng.random() < 0.12:
        return {"author": author, "text": rng.choice(AMBIGUOUS_REPLIES)}
    return {"author": author, "text": rng.choice(STABLE_REPLIES)}


def write_cohort(size: int = None, seeded: int = None, seed: int = None
                 ) -> Dict[str, Any]:
    data = generate_cohort(size, seeded, seed)
    cohort_path = config.DATA_DIR / "cohort.json"
    truth_path = config.EVAL_DIR / "ground_truth.json"
    cohort_path.write_text(json.dumps(data["patients"], indent=2))
    truth_path.write_text(json.dumps(data["ground_truth"], indent=2))
    return {"cohort_path": str(cohort_path), "truth_path": str(truth_path),
            "count": len(data["patients"]),
            "seeded": len(data["ground_truth"]["events"])}


def load_cohort() -> List[Dict[str, Any]]:
    path = config.DATA_DIR / "cohort.json"
    if not path.exists():
        write_cohort()
    return json.loads(path.read_text())


def load_ground_truth() -> Dict[str, Any]:
    return json.loads((config.EVAL_DIR / "ground_truth.json").read_text())


if __name__ == "__main__":
    print(json.dumps(write_cohort(), indent=2))
