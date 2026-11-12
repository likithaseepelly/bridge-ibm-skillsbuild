# IBM Bob task log

## How these sessions were run, stated plainly

All six tasks below were run on 11 November 2026 from the IBM Bob account of
Likitha Seepelly, on the provisioned ibm-skillsbuild-ell instance, during a
joint working session. The team worked through the components together and each
member directed the task covering their own component, but every task was
submitted from one account because the other members could not sign in to Bob
on the day.

These are therefore six genuine Bob task sessions from one account, not five
separate per-member sessions. Where a member later gains access to their own
Bob account, they should rerun their own task and the session record here
should be replaced with theirs.

| Task | Component | Directed by | Task Id |
| --- | --- | --- | --- |
| 01 | Interpretation and escalation agents | Likitha Seepelly | 21d6eb5c3adca82a34b20375665d09d3 |
| 02 | Orchestrator and dry run mode | Gyana Lakshmi Priyanka Ede | 51b884d155bf6fab5918bbbe0a0c219d |
| 03 | Synthetic data and knowledge corpus | Kusuma Phani Sree Karri | a41ed9daa8462268e4cbd6d5b469c |
| 04 | Outreach message quality | Sriram Gurram | 3b15ca76e9a3ca6ae532a26d027ba |
| 05 | Ranking and nurse worklist | Tulasi Nama | 8541ec1193194dd |
| 06 | Cross component regression fix | whole team | 8e46efe6f0d56d2e |

Workspace for every task: bridge.
Bobcoins consumed across all six tasks: roughly 5.5 of the team allowance of 40.

---

## Task 01, interpretation and escalation

Asked Bob to add ten more realistic patient and caregiver reply phrasings to
the test suite, including misspellings and messages that open reassuringly and
end with a worrying detail, then fix the interpreter for the cases it got
wrong, without weakening the rule that an ambiguous reply is never resolved by
guessing or the rule that any emergency phrase sets concern to urgent.

Bob found four defects:
- Urgent terms matched only exact spellings, so cant breath, cannot breethe,
  confuzed and not making any sence were all read as non urgent.
- slept sitting up was mis-scored because only the present tense sleep sitting
  up was listed. That would have under-ranked a deteriorating heart failure
  patient.
- No handling of hedging, so she seems alright i think was read as reassurance
  rather than ambiguity. Bob added a hedge term category.
- The ambiguity word limit was too tight at four words, raised to five.

Both hard rules left intact. Test suite 23 to 33, all passing.

## Task 02, orchestrator dry run

Added build_cycle_plan, a dry run that prints what the cycle would do for each
patient on a given day and why, without writing to the database, exposed as a
--dry-run DAY flag on run_demo.py. Added a DryRunTests class with three tests,
including one asserting that database row counts are identical before and
after a dry run, and one asserting that a patient with a corrupted plan still
appears in the result with an error field rather than being skipped.

## Task 03, third condition

Added type 2 diabetes alongside heart failure and COPD. Bob wrote
knowledge/type2_diabetes_discharge.md from public patient education guidance,
added the medication list and decline reply phrasings to synth.py, added the
condition to CONDITIONS in config.py, and updated the knowledge doc map so
plan intake can retrieve grounded passages for the new condition. Bob also ran
an explicit personal information check and confirmed no generated field
contains PII: names come from a fixed invented list, age is a band rather than
a date of birth, and there is no address, phone, email, SSN, MRN, NHS number
or insurance identifier anywhere in the record.

## Task 04, outreach message quality

Rewrote the check in templates so they read as a person wrote them, and added
a caregiver variant used when the patient record has caregiver_contact set.
Added a ReadabilityTests class with an inline Flesch Kincaid implementation and
no third party packages, asserting that every composed patient message and
every caregiver message across a nineteen day window stays at or below grade
seven.

## Task 05, worklist filters and mobile evidence trail

Added open case and gone quiet filters to the worklist as query parameters with
filter links in the header, including a correct empty state message for each
filter rather than the generic nothing ranked yet. Restacked the evidence trail
rows for a 360 pixel viewport with tap targets of at least forty four pixels
and no horizontal overflow. The approval queue, audit log and degraded banner
were all kept, and no label implying a patient is safe was added.

## Task 06, cross component regression found and fixed

After task 03 the evaluation harness showed the median cycles to detection had
risen from 1 to 4 while the detection rate stayed at 89 percent. The cause was
that RISING_TERMS in the interpretation agent only covered heart failure and
COPD wording, so diabetes decline replies such as blood sugar readings have
been very high the last two days and feeling much more thirsty than usual were
scored mild instead of rising. Four of the nine seeded deterioration patients
were diabetes patients, so their decline was being under-ranked.

Bob extended RISING_TERMS with the diabetes warning wording drawn from the
knowledge file and added tests asserting that every diabetes decline phrase in
synth.py scores rising or higher. Median cycles to detection came back down to
2.5 and the number of top five slots occupied by genuine seeded deterioration
rose from 57 to 83. Both hard rules remained intact.

---

## State after task 06, verified independently

- 56 tests, all passing
- Detection rate 89 percent, 8 of 9 seeded deterioration events
- Median cycles to detection 2.5, worst case 5
- Deferred urgent replies 0
- Ranked entries with no reason 0 of 1075
- Ranked entries with no evidence 0 of 1075
- Injected agent failures surfaced 2 of 2, none skipped
