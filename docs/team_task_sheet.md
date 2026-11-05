# What each person does, in their own IBM Bob account

Send this to the team. Each person needs roughly one hour, signed in to their
own Bob account on the provisioned `ibm-skillsbuild-ell` instance.

The code already exists in this repository. Nobody is building from nothing.
The job is to work the component through Bob, make it better, and capture the
session summary.

---

## Before you start, every person

1. Sign in to IBM Bob with your IBMid, using the email you registered with.
2. In Bob IDE, Settings then General, confirm you are on the
   `ibm-skillsbuild-ell` instance and not a personal account.
3. Confirm you are on Bob IDE v2.0.2 or later.
4. Clone the repository and run it once so you know it works:

```
python3 run_demo.py --no-serve
python3 -m unittest discover -s tests
```

## The rule that cannot be skipped

Open the Bob task, do the work, then **before you close it**:

1. In the Bob chat interface, open Tasks.
2. Use the All filter if your tasks span more than one workspace.
3. Select the task header to reveal the task session consumption summary,
   showing context length, task id, workspace, tokens, cache and API cost.
4. Screenshot it.
5. Save as `firstname_task_01.png` in the `bob_sessions` folder and commit it.

This is a hard requirement for judging eligibility and it cannot be recreated
afterwards. One person's screenshots do not cover the team.

## Bobcoins

Forty, shared across all five of you. Write your prompt before you open the
task. One task per person. Do not explore inside Bob.

---

## Likitha Seepelly, Team Lead

**Component:** interpretation and escalation, `bridge/agents/interpretation.py`
and `bridge/agents/escalation.py`.

Paste into a Bob task:

```
Open bridge/agents/interpretation.py and bridge/agents/escalation.py in this
repository. The interpretation agent reads a free text reply from a patient or
caregiver and returns plan step status, concern level, an ambiguity flag, a
confidence and the phrases it based the decision on. The escalation agent runs
independently and raises a case on an urgent reply, on persistent ambiguity
after one clarifying question, and on silence beyond the plan limit.

Add ten more realistic reply phrasings to the test suite in
tests/test_rules.py, including texts written by a relative rather than the
patient, misspellings, and messages that mix a reassuring opening with a
worrying detail at the end. Make the interpretation agent handle the ones it
currently gets wrong, without weakening these two rules: an ambiguous reply is
never resolved by guessing, and any emergency phrase sets concern to urgent.
Run python3 -m unittest discover -s tests and make everything pass.
```

## Gyana Lakshmi Priyanka Ede, Technical Lead

**Component:** the orchestrator and watsonx Orchestrate, `bridge/orchestrator.py`.

```
Open bridge/orchestrator.py in this repository. It runs one daily cycle over a
cohort: status join, outreach where due, inbound replies, interpretation,
escalation, then ranking. On any agent failure it raises the affected patient
to the nurse and marks the list degraded rather than skipping them.

Two jobs. First, add a dry run mode that prints the cycle plan for a given day
without writing to the database, so the cycle can be explained in a demo.
Second, define the seven agents in IBM watsonx Orchestrate, matching the
responsibilities table in README.md, and document in docs/orchestrate_notes.md
what you defined and what you could not. Keep the local orchestrator working so
the prototype still runs without a cloud dependency.
```

## Kusuma Phani Sree Karri, Architect

**Component:** synthetic data and the retrieval corpus, `bridge/synth.py` and
`knowledge/`.

```
Open bridge/synth.py and the knowledge folder in this repository. The generator
builds sixty synthetic patients, scripts deterioration into nine of them, and
writes the ground truth to eval/ground_truth.json where no agent reads it.

Add a third condition alongside heart failure and COPD, using publicly
available patient education guidance for the warning signs, and write it into
knowledge/ as a new markdown file in the same shape as the existing two. Add
the medication list and the reply phrasings for that condition to synth.py.
Keep the rule that every warning sign carries the id of the passage it came
from. Confirm no field in any generated record contains personal information,
and run the test suite.
```

## Sriram Gurram, General Member

**Component:** outreach and the check in content, `bridge/agents/outreach.py`.

```
Open bridge/agents/outreach.py in this repository. It composes one check in
message for one patient on one day. The rules are enforced in code, not left to
a prompt: under thirty words, exactly one question, plain language, never
clinical advice, never a statement that the patient is fine, and always held
for nurse approval.

Improve the message templates so they read like a person wrote them rather than
a system, and add a caregiver variant for patients where a relative is the
contact. Add a readability check that fails the test suite if a message exceeds
a sixth grade reading level. Do not weaken any existing rule. Run the tests.
```

## Tulasi Nama, Architect

**Component:** ranking and the nurse worklist, `bridge/agents/ranking.py` and
`bridge/server.py`.

```
Open bridge/agents/ranking.py and bridge/server.py in this repository. Ranking
orders the cohort each cycle on change against each patient's own baseline and
writes a one sentence reason plus the evidence ids. The worklist shows the top
five with the reason, the evidence trail, an approval queue and an audit log.

Two jobs. First, add a filter to the worklist so the nurse can show only open
cases or only patients who have gone quiet. Second, make the evidence trail
easier to scan on a phone, since this is used away from a desk. Do not remove
the approval queue, the audit log or the degraded banner, and do not add any
label that implies a patient is safe. Run the tests and open the worklist to
check it.
```

---

## When everyone is done

1. All screenshots committed to `bob_sessions`.
2. `python3 -m unittest discover -s tests` passes.
3. `python3 eval/run_eval.py` runs and the numbers are copied into README.md.
4. Someone fills the brackets in `docs/technology_statement.md` from what
   actually happened in Bob.
