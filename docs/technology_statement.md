# Written technology statement

Paste into the Submissions field on the My Team page. Under 500 words.

> Everything below is real and is backed by the six task session screenshots
> and the task log in `bob_sessions/`. Two brackets remain, on watsonx. Fill or
> delete them before submitting.

---

**IBM Bob.** Bob was the development environment for this build. Each component
went through Bob as its own task, so every session summary maps onto one part
of the system. Six tasks were run on the provisioned `ibm-skillsbuild-ell`
instance, consuming about 5.5 of our 40 shared Bobcoins. Task ids, prompts and
outcomes are recorded in `bob_sessions/task_log.md`.

Bob was not used to generate the system. It was used to attack it. The clearest
example is the interpretation agent, which decides what a patient reply means.
We asked Bob to invent harder reply phrasings and then fix whatever broke. It
found four defects we had missed: urgent terms matched only exact spellings, so
"cant breath" and "not making any sence" were read as non urgent; the phrase
"slept sitting up" was mis-scored because only the present tense was listed,
which would have under-ranked a deteriorating heart failure patient; hedged
replies such as "she seems alright i think" were read as reassurance rather
than ambiguity; and the ambiguity word limit was one word too tight.

The most useful task was one we did not plan. After Bob added type 2 diabetes
as a third condition, our evaluation harness showed median cycles to detection
rising from 1 to 4 while the detection rate held at 89 percent. The cause was a
cross-component gap: the rising-concern term list still only covered heart
failure and COPD, so diabetes decline replies like "blood sugar readings have
been very high the last two days" scored mild instead of rising, and four of
nine seeded deterioration patients were being under-ranked. Bob extended the
term list from the condition's own guidance file and added tests pinning every
diabetes decline phrase. Median detection came back to 2.5 cycles and genuine
deterioration rose from 57 to 83 of the top-five slots.

Across the six tasks the suite grew from 23 tests to 56, all passing, with zero
deferred urgent replies throughout. Bob also ran an explicit check confirming no
generated record contains personal information.

**IBM watsonx.ai.** The interpretation agent calls watsonx.ai for a Granite
second opinion on each reply. The integration is in `bridge/llm.py` and
activates when `WATSONX_API_KEY`, `WATSONX_URL` and `WATSONX_PROJECT_ID` are
set. The constraint is enforced in code: Granite may raise a concern level,
never lower one, and is never asked to resolve ambiguity. Without credentials
the system falls back to its deterministic rule engine, which is what makes our
published numbers reproducible by anyone who clones the repository. [State
whether the demo ran with watsonx credentials or on the rule engine.]

**IBM watsonx Orchestrate.** [State what the team did there: which agents were
defined, or that the instance was provisioned and the cycle modelled locally in
`bridge/orchestrator.py` without deploying.]

**Everything else.** Python 3 standard library only, SQLite for state and an
append-only audit log, a TF-IDF passage index for retrieval grounding, and a
standard library HTTP server for the nurse worklist. No third party packages.

**Data.** Synthetic throughout. No personal information, no client data, no
real patient record. Ground truth lives in `eval/ground_truth.json` and is never
read by any agent.
