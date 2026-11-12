# Written technology statement

Paste into the Submissions field on the My Team page. Under 500 words.

> Every figure below is reproducible. Bob evidence is in `bob_sessions/`. The
> two evaluation runs are in `out/eval_results_rules.json` and
> `out/eval_results_granite.json`.

---

**IBM Bob.** Bob was our development environment. Each component went through
Bob as its own task, so every session summary maps onto one part
of the system. Six tasks ran on the provisioned `ibm-skillsbuild-ell` instance,
using about 5.5 of our 40 shared Bobcoins. Task ids, prompts and outcomes are
in `bob_sessions/task_log.md`.

Bob was not used to generate the system. It was used to attack it. We asked it
to invent harder patient replies and fix whatever broke. It found four defects we
had missed, including urgent terms matched only on exact spelling, so "cant
breath" read as non urgent, and hedges like "she seems alright i think" read as
reassurance, not ambiguity.

The most useful task was unplanned. After Bob added type 2 diabetes
as a third condition, our harness showed median cycles to detection rising from
1 to 4 while the detection rate held at 89 percent and hid it. The rising
concern term list still covered only heart failure and COPD, so diabetes
decline replies scored mild instead of rising and four of nine seeded patients
were under-ranked. Bob extended the list from that condition's guidance file
and added tests pinning every diabetes decline phrase. Median detection
returned to 2.5 cycles and genuine deterioration rose from 57 to 83 of the top
five slots. Across six tasks the suite grew from 23 tests to 56, all passing.

**IBM watsonx.ai.** The interpretation agent sends every non-urgent reply to
Granite for a second opinion, in `bridge/llm.py`. The constraint is enforced in
code: Granite may raise a concern level, never lower one, and never resolves an
ambiguous reply.

We ran the full thirty day evaluation both ways. On `ibm/granite-4-h-small`,
547 calls were made and 547 answered, none falling back. Granite raised
detection from 8 of 9 seeded events to 9 of 9, cut median detection from 2.5
cycles to 2, and moved real deterioration from 83 to 90 of the 145 top five
slots, with false positives unchanged at 5. The patient the rules missed had
written "More out of breath getting dressed than I was last week." No listed
phrase matched, so the rule engine scored it mild. Granite read the comparison
and scored it rising, three days earlier.

Our published headline numbers are the rule engine run, which reproduces for
anyone who clones the repository.

**IBM watsonx Orchestrate.** Not used. The seven agents and the daily cycle are
defined and run in `bridge/orchestrator.py`, keeping the prototype free of a
cloud dependency. Orchestrate is where this cycle would be hosted in
production.

**Everything else.** Python 3 standard library only: SQLite for state and an
append-only audit log, a TF-IDF index for retrieval grounding, and a standard
library HTTP server for the worklist.

**Data.** Synthetic throughout. No personal information, no real patient
record. Ground truth lives in `eval/ground_truth.json` and is never read by an
agent.
