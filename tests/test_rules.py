"""Tests for the rules that are not allowed to break.

These cover the hard constraints from the week 5 governance work, not the happy
path. Run with: python3 -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bridge import config, orchestrator, synth  # noqa: E402
from bridge.agents import (escalation, interpretation, outreach,  # noqa: E402
                           plan_intake, ranking)
from bridge.store import Store  # noqa: E402

RECORD = {
    "patient_id": "T001",
    "name": "Test Patient",
    "condition": "heart_failure",
    "discharge_date": "2026-11-01",
    "age_band": "75 to 84",
    "lives_alone": True,
    "caregiver_contact": True,
    "medications": [{"name": "Furosemide 40 mg", "schedule": "once each morning"}],
    "followup_day": 10,
    "_sim": {"trajectory": "stable", "onset_day": None, "urgent": False,
             "collects_prescription_day": 2, "books_appointment_day": 5,
             "reply_rate": 1.0},
}


class PlanIntakeTests(unittest.TestCase):
    def test_every_warning_sign_has_a_source(self):
        plan = plan_intake.build_plan(RECORD)
        self.assertTrue(plan["warning_signs"])
        for sign in plan["warning_signs"]:
            self.assertTrue(sign["source_id"],
                            "warning sign with no grounded source: %s" % sign)

    def test_lives_alone_gets_shorter_silence_limit(self):
        plan = plan_intake.build_plan(RECORD)
        self.assertEqual(plan["acuity"], "high")
        self.assertLessEqual(plan["silence_limit_days"], 2)


class OutreachTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan_intake.build_plan(RECORD)

    def test_message_is_under_the_word_limit(self):
        for day in range(1, 20):
            msg = outreach.compose(RECORD, self.plan, day)
            self.assertLessEqual(len(msg["text"].split()), outreach.MAX_WORDS)

    def test_exactly_one_question(self):
        for day in range(1, 20):
            msg = outreach.compose(RECORD, self.plan, day)
            self.assertEqual(msg["text"].count("?"), 1, msg["text"])

    def test_never_gives_advice_and_never_says_fine(self):
        for day in range(1, 20):
            msg = outreach.compose(RECORD, self.plan, day)
            self.assertEqual(msg["rule_violations"], [], msg["text"])

    def test_always_held_for_approval(self):
        msg = outreach.compose(RECORD, self.plan, 3)
        self.assertEqual(msg["status"], "hold_for_approval")


class InterpretationTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan_intake.build_plan(RECORD)

    def test_urgent_phrase_sets_urgent(self):
        for text in ["I have chest pain and it is not going away.",
                     "He is confused this morning and not making sense.",
                     "His lips look blue and he is very drowsy."]:
            r = interpretation.interpret(text, self.plan)
            self.assertEqual(r["concern_level"], "urgent", text)

    def test_ambiguous_is_flagged_and_not_guessed(self):
        for text in ["ok", "not sure really", "same i suppose", "cant say"]:
            r = interpretation.interpret(text, self.plan)
            self.assertTrue(r["ambiguity_flag"], text)
            self.assertEqual(r["concern_level"], "unknown", text)

    def test_empty_reply_is_ambiguous_not_reassuring(self):
        r = interpretation.interpret("", self.plan)
        self.assertTrue(r["ambiguity_flag"])
        self.assertNotEqual(r["concern_level"], "none")

    def test_reassuring_reply_is_not_escalated(self):
        r = interpretation.interpret(
            "All good here thanks. Picked up the tablets yesterday.", self.plan)
        self.assertEqual(r["concern_level"], "none")
        self.assertEqual(r["plan_step_status"].get("prescription_collected"),
                         "complete")

    def test_rising_reply_is_detected(self):
        r = interpretation.interpret(
            "Scale is up four pounds since Monday and the shoes are tight.",
            self.plan)
        self.assertEqual(r["concern_level"], "rising")


class EscalationTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan_intake.build_plan(RECORD)

    def test_urgent_is_raised_immediately(self):
        interps = [{"concern_level": "urgent", "phrases": ["chest pain"], "day": 4}]
        case = escalation.evaluate("T001", 4, self.plan, interps, 4, 0)
        self.assertIsNotNone(case)
        self.assertEqual(case["trigger"], "urgent_reply")
        self.assertTrue(case["show_emergency_guidance"])

    def test_urgent_outranks_everything_else(self):
        interps = [{"concern_level": "urgent", "phrases": ["chest pain"], "day": 9}]
        case = escalation.evaluate("T001", 20, self.plan, interps, None, 3)
        self.assertEqual(case["trigger"], "urgent_reply")

    def test_ambiguity_escalates_after_one_clarifying_question(self):
        interps = [{"concern_level": "unknown", "ambiguity_flag": True,
                    "phrases": ["ok"], "day": 5}]
        self.assertIsNone(
            escalation.evaluate("T001", 5, self.plan, interps, 5, 0))
        case = escalation.evaluate("T001", 6, self.plan, interps, 6, 1)
        self.assertEqual(case["trigger"], "persistent_ambiguity")

    def test_silence_is_a_signal(self):
        case = escalation.evaluate("T001", 9, self.plan, [], 4, 0)
        self.assertEqual(case["trigger"], "extended_silence")

    def test_escalation_agent_never_closes_a_case(self):
        source = Path(escalation.__file__).read_text()
        self.assertNotIn("close_case", source)


class RankingTests(unittest.TestCase):
    def test_every_entry_has_a_reason_and_evidence(self):
        db = Path(tempfile.mkdtemp()) / "t.db"
        store = Store(db)
        cohort = synth.generate_cohort(size=20, seeded=4, seed=7)["patients"]
        orchestrator.bootstrap(store, cohort)
        orchestrator.simulate(store, days=10)
        for day in range(1, 11):
            for row in store.ranking(day):
                self.assertTrue(row["reason"].strip())
                self.assertTrue(row["evidence_ids"])
        store.close()

    def test_no_output_ever_declares_a_patient_safe(self):
        db = Path(tempfile.mkdtemp()) / "t2.db"
        store = Store(db)
        cohort = synth.generate_cohort(size=20, seeded=4, seed=11)["patients"]
        orchestrator.bootstrap(store, cohort)
        orchestrator.simulate(store, days=8)
        banned = ["safe", "no action needed", "all clear", "fine", "stable"]
        for day in range(1, 9):
            for row in store.ranking(day):
                low = row["reason"].lower()
                for word in banned:
                    self.assertNotIn(" %s" % word, " " + low,
                                     "ranking reason implies safety: %s"
                                     % row["reason"])
        store.close()


class SyntheticDataTests(unittest.TestCase):
    def test_cohort_size_and_seeded_count(self):
        data = synth.generate_cohort(size=40, seeded=6, seed=3)
        self.assertEqual(len(data["patients"]), 40)
        self.assertEqual(len(data["ground_truth"]["events"]), 6)

    def test_no_personal_information_fields(self):
        banned = {"ssn", "social_security", "mrn", "address", "phone", "email",
                  "date_of_birth", "dob", "insurance_id", "nhs_number"}
        for patient in synth.generate_cohort(size=10, seeded=2, seed=5)["patients"]:
            for key in patient:
                self.assertNotIn(key.lower(), banned)
            self.assertNotIn("date_of_birth", patient)
            self.assertIn("age_band", patient)  # band, never a date of birth

    def test_ground_truth_is_separate_from_the_cohort(self):
        data = synth.generate_cohort(size=10, seeded=2, seed=5)
        for patient in data["patients"]:
            self.assertNotIn("first_signal_day", patient)


class PipelineTests(unittest.TestCase):
    def test_no_urgent_reply_is_ever_deferred(self):
        db = Path(tempfile.mkdtemp()) / "t3.db"
        store = Store(db)
        cohort = synth.generate_cohort(size=40, seeded=8, seed=21)["patients"]
        orchestrator.bootstrap(store, cohort)
        orchestrator.simulate(store, days=20)
        for record in store.all_patients():
            pid = record["patient_id"]
            case_days = [c["day"] for c in store.cases_for(pid)
                         if c["trigger"] == "urgent_reply"]
            for interp in store.interpretations_for(pid):
                if interp.get("concern_level") == "urgent":
                    self.assertTrue(
                        any(d <= interp["day"] for d in case_days),
                        "urgent reply on day %d for %s was not raised in the "
                        "same cycle" % (interp["day"], pid))
        store.close()

    def test_agent_failure_raises_the_patient_rather_than_skipping(self):
        db = Path(tempfile.mkdtemp()) / "t4.db"
        store = Store(db)
        cohort = synth.generate_cohort(size=12, seeded=2, seed=31)["patients"]
        orchestrator.bootstrap(store, cohort)
        orchestrator.simulate(store, days=6, fail_on_day=3)
        failures = [c for c in store.open_cases()
                    if c["trigger"] == "system_failure"]
        self.assertTrue(failures, "injected failure was silently swallowed")
        store.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
