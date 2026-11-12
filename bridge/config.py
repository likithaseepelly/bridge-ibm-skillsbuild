"""Shared configuration for the Bridge prototype.

Everything in this project runs on synthetic data. No personal information,
no client data and no real patient records enter the system at any point.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "data" / "synthetic"
KNOWLEDGE_DIR = ROOT / "knowledge"
EVAL_DIR = ROOT / "eval"
OUT_DIR = ROOT / "out"

DB_PATH = OUT_DIR / "bridge.db"

# Cohort settings
COHORT_SIZE = 60
SEEDED_DETERIORATION = 9
WINDOW_DAYS = 30
RANDOM_SEED = 20261105

# Plan step timings, in days after discharge.
PRESCRIPTION_DUE_DAY = 2
APPOINTMENT_BOOKED_DUE_DAY = 7
APPOINTMENT_ATTENDED_DUE_DAY = 14

# Operating rules. These are hard constraints, not tuning knobs.
APPROVAL_MODE = True          # no message reaches a patient without a nurse
WORKLIST_SIZE = 5             # how many names the nurse sees each morning
MAX_CLARIFYING_QUESTIONS = 1  # then escalate, never guess twice
SILENCE_LIMIT_DAYS = 3        # high acuity plans escalate sooner, see plan_intake

CONDITIONS = ("heart_failure", "copd", "type2_diabetes")

# Optional IBM watsonx.ai inference. If these are not set the system runs on its
# deterministic rule engine, which is what makes the demo reproducible.
WATSONX_API_KEY = os.environ.get("WATSONX_API_KEY", "")
WATSONX_URL = os.environ.get("WATSONX_URL", "")
WATSONX_PROJECT_ID = os.environ.get("WATSONX_PROJECT_ID", "")
WATSONX_MODEL_ID = os.environ.get("WATSONX_MODEL_ID", "ibm/granite-3-8b-instruct")


def watsonx_configured() -> bool:
    return bool(WATSONX_API_KEY and WATSONX_URL and WATSONX_PROJECT_ID)


for _d in (DATA_DIR, OUT_DIR, EVAL_DIR):
    _d.mkdir(parents=True, exist_ok=True)
