"""Tests for the rules that are not allowed to break.

These cover the hard constraints from the week 5 governance work, not the happy
path. Run with: py -m unittest discover -s tests -v
"""

import os
import re
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

RECORD_NO_CAREGIVER = dict(RECORD, caregiver_contact=False, patient_id="T002")

# ---------------------------------------------------------------------------
# Inline Flesch-Kincaid Grade Level helpers — no third-party packages.
# Formula: FK_GL = 0.39 * (words / sentences) + 11.8 * (syllables / words) - 15.59
# A result <= 7.0 is considered sixth-grade or below.
# ---------------------------------------------------------------------------

def _count_syllables(word: str) -> int:
    """Count syllables in a single word using a vowel-run heuristic."""
    word = word.lower().strip(".,!?;:\"'()-")
    if not word:
        return 0
    # Each group of consecutive vowels counts as one syllable, with two adjustments:
    # 1. A silent trailing 'e' is not a syllable on its own (e.g. "come", "have").
    # 2. Every word has at least one syllable.
    vowels = "aeiouy"
    count = 0
    prev_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    # Subtract silent trailing 'e' when preceded by a consonant and word > 2 chars.
    if len(word) > 2 and word[-1] == "e" and word[-2] not in vowels:
        count -= 1
    return max(1, count)


def _fk_grade(text: str) -> float:
    """Return the Flesch-Kincaid Grade Level for *text*."""
    # Split into sentences on '.', '!', '?'.
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    num_sentences = max(1, len(sentences))
    words = [w for w in re.split(r"\s+", text) if w.strip()]
    num_words = max(1, len(words))
    num_syllables = sum(_count_syllables(w) for w in words)
    return (0.39 * (num_words / num_sentences)
            + 11.8 * (num_syllables / num_words)
            - 15.59)

# FK grade level at or below this value is considered sixth grade.
FK_SIXTH_GRADE = 7.0


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

    def test_caregiver_variant_used_when_caregiver_contact_set(self):
        """When caregiver_contact is truthy the message must not address the
        patient by first name in the opening (it goes to the caregiver)."""
        for day in range(1, 20):
            msg = outreach.compose(RECORD, self.plan, day)
            self.assertTrue(msg["caregiver_variant"],
                            "caregiver_variant flag not set for day %d" % day)

    def test_no_caregiver_variant_without_caregiver_contact(self):
        """When caregiver_contact is absent the patient-directed template is used."""
        for day in range(1, 20):
            msg = outreach.compose(RECORD_NO_CAREGIVER, self.plan, day)
            self.assertFalse(msg["caregiver_variant"],
                             "caregiver_variant unexpectedly set for day %d" % day)


class ReadabilityTests(unittest.TestCase):
    """Every composed message must be at or below a sixth-grade reading level.

    Flesch-Kincaid Grade Level is computed inline using a simple syllable
    heuristic — no third-party packages required.
    """

    def setUp(self):
        self.plan = plan_intake.build_plan(RECORD)
        self.plan_nc = plan_intake.build_plan(RECORD_NO_CAREGIVER)

    def _assert_readable(self, msg: dict) -> None:
        grade = _fk_grade(msg["text"])
        self.assertLessEqual(
            grade, FK_SIXTH_GRADE,
            "Message exceeds sixth-grade reading level (FK=%.2f): %r"
            % (grade, msg["text"]),
        )

    def test_patient_templates_all_sixth_grade_or_below(self):
        for day in range(1, 20):
            msg = outreach.compose(RECORD_NO_CAREGIVER, self.plan_nc, day)
            self._assert_readable(msg)

    def test_caregiver_templates_all_sixth_grade_or_below(self):
        for day in range(1, 20):
            msg = outreach.compose(RECORD, self.plan, day)
            self._assert_readable(msg)

    def test_clarify_step_sixth_grade_or_below(self):
        msg = outreach.compose(RECORD, self.plan, 5, needs_clarification=True)
        self._assert_readable(msg)

    def test_clarify_step_no_caregiver_sixth_grade_or_below(self):
        msg = outreach.compose(RECORD_NO_CAREGIVER, self.plan_nc, 5,
                               needs_clarification=True)
        self._assert_readable(msg)


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

    # --- ten additional phrasings ---

    def test_relative_message_reassuring_start_urgent_end(self):
        # Opens reassuringly but closes with an emergency detail — must be urgent.
        text = ("This is his wife. He has been fine all week but this morning "
                "he said he had chest pain and could not get comfortable.")
        r = interpretation.interpret(text, self.plan)
        self.assertEqual(r["concern_level"], "urgent", text)

    def test_relative_message_with_swelling_and_orthopnoea(self):
        # Caregiver reports swelling and having to sleep sitting up — rising.
        text = ("My mum is doing okay but her feet are very swollen and she "
                "slept sitting up last night.")
        r = interpretation.interpret(text, self.plan)
        self.assertEqual(r["concern_level"], "rising", text)

    def test_misspelled_breathe_is_still_urgent(self):
        # Common misspelling: "breethe" — must still trigger urgent.
        text = "cant breethe properly, feels tight"
        r = interpretation.interpret(text, self.plan)
        self.assertEqual(r["concern_level"], "urgent", text)

    def test_misspelled_cant_breath_is_still_urgent(self):
        # "breath" instead of "breathe" — common patient error, must be urgent.
        text = "Doing ok but i feel like i cant breath at all today"
        r = interpretation.interpret(text, self.plan)
        self.assertEqual(r["concern_level"], "urgent", text)

    def test_misspelled_confused_is_still_urgent(self):
        # Daughter writes, misspells "confused" and "sense" — must be urgent.
        text = ("I'm his daughter writing this. Dad is confuzed today and not "
                "making any sence.")
        r = interpretation.interpret(text, self.plan)
        self.assertEqual(r["concern_level"], "urgent", text)

    def test_reassuring_opener_with_rising_detail_is_rising(self):
        # "Feeling much better, no problems at all" is cancelled by "scale is up".
        text = ("Feeling much better, no problems at all, but the scale is up "
                "three pounds this morning.")
        r = interpretation.interpret(text, self.plan)
        self.assertEqual(r["concern_level"], "rising", text)

    def test_caregiver_reports_collapse(self):
        # Third-person report of collapse — urgent regardless of who writes.
        text = "She collapsed in the kitchen just now."
        r = interpretation.interpret(text, self.plan)
        self.assertEqual(r["concern_level"], "urgent", text)

    def test_hedged_short_reply_is_ambiguous(self):
        # "seems alright i think" hedges the reassurance — must be ambiguous.
        text = "She seems alright i think"
        r = interpretation.interpret(text, self.plan)
        self.assertTrue(r["ambiguity_flag"], text)
        self.assertEqual(r["concern_level"], "unknown", text)

    def test_relative_passed_out_is_urgent(self):
        # Relative uses past tense of faint — still an emergency phrase.
        text = "He is fine now but earlier he had passed out for a moment."
        r = interpretation.interpret(text, self.plan)
        self.assertEqual(r["concern_level"], "urgent", text)

    def test_reassuring_opener_with_gasping_is_urgent(self):
        # Reassuring start then reveals patient is gasping — urgent must win.
        text = ("Everything seemed okay this morning but now he is gasping and "
                "cannot catch his breath.")
        r = interpretation.interpret(text, self.plan)
        self.assertEqual(r["concern_level"], "urgent", text)


class DiabetesDeclineTests(unittest.TestCase):
    """Every diabetes decline phrase from synth.T2D_DECLINE must score
    rising or higher.  The list also covers the extended wording from the
    knowledge file that the user explicitly asked to support."""

    def setUp(self):
        self.plan = plan_intake.build_plan(
            dict(RECORD, condition="type2_diabetes"))

    def _assert_rising_or_urgent(self, text: str) -> None:
        r = interpretation.interpret(text, self.plan)
        self.assertIn(
            r["concern_level"], ("rising", "urgent"),
            "Expected rising or urgent for %r but got %r"
            % (text, r["concern_level"]))

    # --- phrases taken directly from synth.T2D_DECLINE ---

    def test_high_blood_sugar_readings(self):
        self._assert_rising_or_urgent(
            "Blood sugar readings have been very high the last two days.")

    def test_thirsty_and_toilet(self):
        self._assert_rising_or_urgent(
            "Feeling much more thirsty than usual and going to the toilet a lot.")

    def test_foot_sore_swollen(self):
        self._assert_rising_or_urgent(
            "Foot is red and swollen where the sore is, does not look right.")

    def test_feeling_sick_high_sugar(self):
        self._assert_rising_or_urgent(
            "Feeling sick and stomach hurts, sugar was very high this morning.")

    # --- additional phrasing from the knowledge file ---

    def test_persistently_high_blood_sugar(self):
        self._assert_rising_or_urgent(
            "Blood sugar has been persistently high for three days now.")

    def test_much_more_thirsty(self):
        self._assert_rising_or_urgent(
            "He has been much more thirsty than usual since yesterday.")

    def test_passing_more_urine(self):
        self._assert_rising_or_urgent(
            "She is passing more urine than usual overnight.")

    def test_feeling_sick_alongside_high_sugar(self):
        self._assert_rising_or_urgent(
            "Feeling sick and vomiting alongside high sugar readings today.")

    def test_wound_not_healing(self):
        self._assert_rising_or_urgent(
            "The wound on her foot is not healing and looks red.")

    def test_foot_sore_not_healing(self):
        self._assert_rising_or_urgent(
            "There is a foot sore that does not seem to be healing at all.")

    def test_blurred_vision(self):
        self._assert_rising_or_urgent(
            "His vision has gone blurred which is new since discharge.")

    def test_blurred_vision_worsening(self):
        self._assert_rising_or_urgent(
            "Blurred vision that is new or worsening over the last two days.")

    # --- confirm the ambiguity and emergency rules are still intact ---

    def test_ambiguity_rule_not_weakened(self):
        """Single-word or heavily-hedged replies must still be unknown."""
        for text in ["ok", "not sure really", "same i suppose"]:
            r = interpretation.interpret(text, self.plan)
            self.assertEqual(r["concern_level"], "unknown", text)
            self.assertTrue(r["ambiguity_flag"], text)

    def test_emergency_rule_not_weakened(self):
        """Emergency phrase still sets concern to urgent for a diabetes patient."""
        r = interpretation.interpret(
            "I have chest pain and it is not going away.", self.plan)
        self.assertEqual(r["concern_level"], "urgent")


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


class DryRunTests(unittest.TestCase):
    """Dry-run mode must not write anything to the database."""

    def _make_store(self):
        db = Path(tempfile.mkdtemp()) / "dr.db"
        store = Store(db)
        cohort = synth.generate_cohort(size=10, seeded=2, seed=42)["patients"]
        orchestrator.bootstrap(store, cohort)
        orchestrator.simulate(store, days=5)
        return store

    def test_dry_run_writes_nothing(self):
        """build_cycle_plan must leave every table row count unchanged."""
        store = self._make_store()
        before = orchestrator._row_counts(store)
        orchestrator.build_cycle_plan(store, 6)
        after = orchestrator._row_counts(store)
        self.assertEqual(before, after,
                         "dry-run wrote to the database: %s"
                         % {t: after[t] - before[t]
                            for t in after if after[t] != before[t]})
        store.close()

    def test_dry_run_returns_one_entry_per_patient(self):
        """build_cycle_plan must return exactly one entry per patient."""
        store = self._make_store()
        patients = store.all_patients()
        plan = orchestrator.build_cycle_plan(store, 6)
        self.assertEqual(len(plan), len(patients))
        store.close()

    def test_dry_run_failure_entry_not_skipped(self):
        """A patient whose plan computation fails must still appear in the
        returned list with an error field, not be silently omitted."""
        store = self._make_store()
        patients = store.all_patients()
        # Corrupt one plan so plan processing will fail inside build_cycle_plan.
        pid = patients[0]["patient_id"]
        store.conn.execute(
            "UPDATE plans SET plan_json = 'INVALID_JSON' WHERE patient_id = ?",
            (pid,))
        store.conn.commit()
        before = orchestrator._row_counts(store)
        plan = orchestrator.build_cycle_plan(store, 6)
        after = orchestrator._row_counts(store)
        # Row counts must be unchanged even on error.
        self.assertEqual(before, after,
                         "dry-run with failing patient wrote to the database")
        pids_in_plan = [e["patient_id"] for e in plan]
        self.assertIn(pid, pids_in_plan,
                      "failing patient was silently skipped instead of raised")
        failing = next(e for e in plan if e["patient_id"] == pid)
        self.assertIsNotNone(failing["error"],
                             "failing patient entry has no error field")
        store.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
