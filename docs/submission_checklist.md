# Submission checklist

Everything the programme asks for, in the order to do it.

Deadline on the Complete the learning lab page and in the coach email:
**November 22, 2026.** The same page also says assemble and submit by
November 8. Ask Chiamaka in Slack which one governs and write the answer here:
`____________`.

---

## Step 1, GitHub repository

One person creates it. It must be public, or the evaluators cannot open it.

```
cd bridge
git init
git add .
git commit -m "Bridge, post-discharge agentic care transition system"
git branch -M main
git remote add origin https://github.com/<owner>/bridge-ibm-skillsbuild.git
git push -u origin main
```

Then open the URL in a private browser window. If it asks you to sign in, it is
not public.

- [ ] Repository is public
- [ ] README.md renders on the front page
- [ ] `bob_sessions/` contains screenshots from every member
- [ ] `docs/` contains both statements and the demo script

## Step 1b, IBM watsonx.ai, verified 11 November 2026

Live and answering on `ibm/granite-4-h-small` in Dallas. 547 calls, 547
answered, nothing fell back. Detection went from 8 of 9 to 9 of 9 against the
rule engine, with false positives unchanged. Both result files are committed.

If you need to rerun it, set the three variables and check before you run:

```
$env:WATSONX_URL        = "https://us-south.ml.cloud.ibm.com"
$env:WATSONX_PROJECT_ID = "b0a712db-5e49-4dd9-ab2e-1e67051efc06"
$env:WATSONX_API_KEY    = [System.Net.NetworkCredential]::new("", (Read-Host "Paste key" -AsSecureString)).Password
py scripts\check_watsonx.py
```

The project id is not a secret. The API key is. Never paste it into a chat, a
screenshot, a commit or this file. If one is ever exposed, delete it at
cloud.ibm.com under Manage, Access (IAM), API keys and make a new one.

## Step 2, the Bob work

Follow `docs/team_task_sheet.md`. Each member, one hour, own account.

- [ ] Likitha, interpretation and escalation
- [ ] Gyana, orchestrator and watsonx Orchestrate
- [ ] Kusuma, synthetic data and knowledge corpus
- [ ] Sriram, outreach content
- [ ] Tulasi, ranking and the worklist
- [ ] Every member has committed their task session screenshots

## Step 3, the prototype link

The submission asks for a publicly accessible link to a working prototype. You
have two options.

**Option A, the repository is the prototype link.** Acceptable, since it clones
and runs with one command and the README says exactly how. Simplest and
safest today.

**Option B, host the worklist.** Deploy `run_demo.py` to any free Python host
and submit that URL. Better for evaluators who will not clone anything. Do this
only if someone has time, and test the link from a private window.

- [ ] Prototype link chosen and tested from a logged out browser

## Step 4, the demo video

Follow `docs/demo_video_script.md`.

- [ ] Recorded, under three minutes
- [ ] Uploaded to YouTube as unlisted or public
- [ ] Link tested in a private window

## Step 5, the two statements

Both are finished. No brackets left, every number checked against a run, and
both are under the 500 word limit with margin. Paste them as they are.

- [ ] `docs/problem_and_solution_statement.md`, 490 words
- [ ] `docs/technology_statement.md`, 487 words

Do not paste the lines above the horizontal rule in either file. Those are
notes to you, not part of the statement.

## Step 6, submit

On the My Team page, Submissions section:

- [ ] Video demonstration URL
- [ ] Problem and solution statement, pasted
- [ ] Technology statement, pasted
- [ ] Working prototype URL
- [ ] Click Submit

If you revise anything later, resubmit **all four** items. The most recent
submission is the one that counts.

## Step 7, completion requirements for the certificate and career fair

These are separate from the project submission and are per person, not per
team.

- [ ] Every member has completed the mandatory self paced SkillsBuild courses
- [ ] Every member has attended the instructor led sessions or watched the
      recordings and marked the activity complete
- [ ] Project documentation and presentation submitted

Anyone who has not finished their own learning plan does not complete the lab,
regardless of what the team submits.

---

## Two honest notes

**Bob session screenshots.** The programme asks for them per member. If only
some members produce them, say so plainly rather than relabelling one person's
files. A shortfall is survivable. A misrepresentation is not.

**Ajay is not on the roster.** The team page shows five of five without him.
Only registered members get the certificate and the career fair invitation.
Raise it with Chiamaka now if that needs fixing.
