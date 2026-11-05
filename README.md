# Bridge

An agentic system for the thirty days after a hospital discharge.

Built for the **IBM SkillsBuild AI Experiential Learning Lab**, Track 1 Smart
Healthcare, by the **FDU AI Experiential Learning Lab team** at Fairleigh
Dickinson University.

> Bridge ranks and raises. It does not diagnose, it does not give clinical
> advice, and it never decides that a patient is safe. Synthetic data only.
> Not a medical device.

---

## The problem

Hospitals manage the stay and manage the follow up visit. The four weeks in
between belong to nobody. Risk is scored on the day the patient leaves and
never recalculated, the single callback usually reaches voicemail, and the care
team learns something went wrong when the patient is readmitted.

A transitional care nurse carries around eighty patients inside their thirty day
window and makes one decision every morning: who do I call first. Today that
decision is made from a list ordered by discharge date.

## What Bridge does

1. **Picks up the plan.** The discharge record becomes a tracked plan with
   expected timings, not a document that is filed.
2. **Asks the patient, briefly.** Short plain language check ins timed around
   that plan. A relative can answer. Every message is held for nurse approval.
3. **Reads the reply.** Status against the plan, concern level, ambiguity flag,
   confidence, and the exact phrases the decision rested on.
4. **Joins what it learns.** Replies sit alongside prescription and appointment
   status as one moving picture per patient.
5. **Re-ranks every day.** The cohort is reordered on change against each
   patient's own baseline, and every position carries a reason in one sentence.
6. **A nurse decides.** Five names, reasons, evidence one click away. Anything
   urgent leaves the cycle immediately and shows emergency guidance.

## Results on the seeded synthetic cohort

Sixty synthetic patients, nine with scripted deterioration, thirty simulated
days, one agent failure injected on day twelve.

| Measure | Result |
| --- | --- |
| Detection rate | 89 percent, 8 of 9 seeded events reached the top five |
| Median cycles to detection | 1 |
| Worst case cycles to detection | 4 |
| Unexplained top five slots | 2 percent of 144 |
| Deferred urgent replies | 0 |
| Ranked entries with no reason or no evidence | 0 of 1111 |
| Injected failures surfaced rather than skipped | 2 of 2 |

Reproduce with `python3 eval/run_eval.py`.

## Run it

Python 3.9 or later. No third party packages required.

```bash
python3 run_demo.py                 # build cohort, run 12 cycles, serve on :8000
python3 run_demo.py --days 20       # run more cycles first
python3 run_demo.py --no-serve      # just the pipeline and a printed summary
python3 eval/run_eval.py            # 30 day replay with the five metrics
python3 -m unittest discover -s tests -v
```

Then open <http://localhost:8000>.

## Architecture

Multi agent with an orchestrator. The work splits into jobs with different
failure modes, so the escalation rule can be audited on its own and a weak
interpretation cannot silently become a ranking.

| Agent | Owns | Never decides |
| --- | --- | --- |
| Orchestrator | The daily cycle, per patient state, retries, logging | Anything clinical |
| Plan Intake | Turning a discharge record into a tracked plan | Any instruction not in the record or a retrieved passage |
| Outreach | Wording, timing, channel, when to stop asking | Never sends without approval, never advises |
| Interpretation | What a reply means, and when it cannot tell | Never resolves ambiguity by guessing |
| Status and Loop | Whether a plan step is complete, pending or failed | Never contacts the patient |
| Triage and Ranking | Order of the list and the reason attached | Never declares a patient safe |
| Escalation and Safety | When to break the cycle and raise a case now | Never closes a case, never suppresses one |

```
bridge/
  config.py          operating rules and watsonx settings
  store.py           SQLite state and the append only audit log
  knowledge.py       retrieval over the discharge guidance corpus
  synth.py           synthetic cohort, scripted deterioration, reply simulator
  llm.py             optional IBM watsonx.ai inference, Granite
  orchestrator.py    the daily cycle
  server.py          the nurse worklist
  agents/            one file per agent
knowledge/           public discharge guidance, the retrieval corpus
data/synthetic/      generated cohort, regenerate any time
eval/                ground truth and the scoring harness
tests/               the rules that are not allowed to break
bob_sessions/        IBM Bob task session screenshots, one set per member
docs/                statements, demo script, screens
```

## IBM technology

- **IBM Bob** is the development environment for the build. See
  `docs/technology_statement.md` and the screenshots in `bob_sessions/`.
- **IBM watsonx.ai** provides inference for reply interpretation when
  credentials are present. Set `WATSONX_API_KEY`, `WATSONX_URL` and
  `WATSONX_PROJECT_ID` and the interpretation agent asks Granite for a second
  opinion. Granite may raise a concern level, never lower one. Without
  credentials the system runs on its deterministic rule engine, which is what
  makes the evaluation reproducible.
- **IBM watsonx Orchestrate** is the intended host for the agents and the daily
  cycle. The orchestrator in this repository mirrors that cycle so the
  prototype runs end to end without a cloud dependency.

## Safety rules, enforced in code

- Never gives clinical advice, a diagnosis, a dose or a treatment instruction.
- Never tells a patient they are fine.
- Never contacts a patient with content a nurse has not approved.
- Never closes a case it raised.
- Never resolves an ambiguous reply by guessing. One clarifying question, then
  a human.
- Never holds an urgent signal for the next cycle.
- Never replaces the emergency pathway.
- Never reads silence as stability.

Each of these has a test in `tests/test_rules.py`.

## Data

Synthetic only. The generator invents names, conditions, medications and
replies. No personal information, no client data and no real patient record
enters the system at any point. The clinical guidance in `knowledge/` is
compiled from publicly available patient education material and is used as
retrieval grounding, with a source id attached to every warning sign the system
tracks.

Ground truth for the evaluation lives in `eval/ground_truth.json` and is never
read by any agent.

## Known limitations

No real patients, no clinical validation, no real messaging gateway, no EHR
integration, English only, heart failure and COPD plans only, and the response
rate the whole loop depends on is assumed rather than measured.
