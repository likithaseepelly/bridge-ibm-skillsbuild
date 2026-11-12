# Three minute demo video, script and shot list

Hard limit is three minutes. Evaluators stop watching at three minutes. At
least ninety seconds must be the solution running on screen, and the use of
IBM Bob must be clearly shown.

Every number in this script is real and reproducible from the repository.
Record at 1920 by 1080. One take per section is fine, cut them together.

**Before you record:** open three things and leave them open.

```
Tab 1    http://localhost:8000          the running worklist
Window   PowerShell in the bridge folder, ready to run the eval
Window   IBM Bob with the Tasks list open
```

Start the app with `py run_demo.py` and leave it running.

---

## 0:00 to 0:25, the problem

**On screen:** a title card, then the team name, then one line of text at a
time as you speak.

**Say:**

> A patient leaves hospital with new medicines, an appointment, and fifteen
> minutes of teaching at the bedside. From that moment, for thirty days, nobody
> is watching. Risk was scored on the day they left and never recalculated. One
> transitional care nurse is carrying eighty of these patients and gets one
> callback attempt each. The care team finds out something went wrong when the
> patient comes back through the emergency department.

## 0:25 to 0:40, what we built

**On screen:** the five step loop, one line each, appearing as you say them.

**Say:**

> Bridge watches those thirty days. It turns the discharge record into a plan
> it tracks, checks in with the patient in short plain messages, reads the
> replies, and every morning hands the nurse five names with a reason beside
> each. It ranks and raises. It never diagnoses, and it never decides anyone is
> safe.

## 0:40 to 2:20, the solution running. This is the part that counts.

**Shot 1, the worklist.** Open the running app.

> This is the nurse's morning. Sixty patients inside their thirty day window.
> Five names. Not ordered by discharge date. Ordered by what has happened since.

**Shot 2, read the top rows.** Point at the reason text, do not just scroll.

> Top of the list reported an emergency sign. Below that, a patient who said
> their weight is up four pounds since Monday, which is worse than their own
> previous reply. Third, someone who has not answered in four days with a
> prescription still uncollected. Silence is a signal here, not reassurance.

**Shot 3, the evidence trail.** Click Evidence on one patient. Scroll it.

> Every position opens to its evidence. What we asked, what came back, what the
> plan expected, what changed. The nurse can see exactly why this person is
> third and not thirtieth, which is the thing a risk score never tells her.

**Shot 4, the filters.** Click the open case filter, then the gone quiet filter.

> She can narrow it to open cases, or to the patients who have stopped
> replying.

**Shot 5, the approval queue.** Click Approvals.

> Nothing reaches a patient without a nurse approving it. This is the queue.

**Shot 6, the urgent path.** Back to the worklist, point at the red banner.

> When a reply contains an emergency phrase it leaves the cycle immediately.
> Emergency guidance goes to the sender and the case is at the top of the list
> in the same cycle. Never held for tomorrow.

**Shot 7, the terminal.** Run `py eval/run_eval.py` and let it finish on camera.
Do this with the watsonx variables unset so it runs on rules and finishes fast.

> We tested it. Sixty synthetic patients across three conditions, nine with
> scripted deterioration, thirty simulated days, and one agent failure injected
> deliberately. Eight of nine surfaced into the top five. Zero urgent replies
> deferred. Every ranked entry carried a reason and traceable evidence, all
> one thousand and seventy five of them. Both injected failures were raised to
> the nurse rather than silently skipped.

**Shot 8, watsonx.ai.** Run `py scripts/check_watsonx.py` on camera. It takes
about five seconds and ends with the model replying. Then cut to the comparison
table in README.md. Do not try to run the full Granite evaluation on camera, it
takes eight minutes.

> Those numbers are the rule engine, with no credentials, so anyone can
> reproduce them. Then we turned on IBM watsonx.ai. Every non urgent reply goes
> to Granite for a second opinion, and Granite is only ever allowed to raise a
> concern level, never lower one.
>
> Five hundred and forty seven calls, five hundred and forty seven answered,
> nothing fell back. Detection went from eight of nine to nine of nine. The
> patient the rules missed had written, more out of breath getting dressed than
> I was last week. No phrase in our list matched that, so the rules called it
> mild. Granite read the comparison with last week and called it rising, three
> days earlier.
>
> False positives did not move. It caught more without crying wolf more.

## 2:20 to 2:45, IBM Bob. Do not rush this part.

**On screen:** the Bob IDE, the Tasks list showing six tasks, then open one
task session summary.

**Say:**

> IBM Bob was our build environment. Six tasks, one per component, all recorded
> here. We did not use Bob to generate the system. We used it to attack it.
>
> The best example was an accident. After Bob added type two diabetes as a
> third condition, our evaluation harness showed detection latency jumping from
> one cycle to four, while the headline detection rate stayed at eighty nine
> percent and hid it. The cause was a gap between two components: the rising
> concern word list still only knew heart failure and COPD wording, so a reply
> saying blood sugar has been very high for two days scored mild instead of
> rising. Four of our nine deteriorating patients were being under ranked.
>
> Bob fixed it from the condition's own guidance file and pinned it with tests.
> Latency came back to two and a half cycles and genuine deterioration in the
> top five went from fifty seven slots to eighty three.

## 2:45 to 3:00, close

**On screen:** the worklist again, then the repository URL.

**Say:**

> Fifty six tests, synthetic data throughout, no personal information anywhere,
> and the whole thing clones and runs with one command. The nurse's job does
> not change. What changes is the quality of the decision she makes at the
> start of each day.

---

## The numbers, so you quote them correctly

| Measure | Value |
| --- | --- |
| Cohort | 60 synthetic patients, 3 conditions |
| Seeded deterioration events | 9 |
| Simulated days | 30 |
| Detection rate | 89 percent, 8 of 9 |
| Median cycles to detection | 2.5 |
| Worst case cycles to detection | 5 |
| Deferred urgent replies | 0 |
| Ranked entries with no reason | 0 of 1075 |
| Ranked entries with no evidence | 0 of 1075 |
| Injected failures surfaced | 2 of 2 |
| Tests | 56, all passing |
| Bob tasks | 6, about 5.5 of 40 Bobcoins |

With IBM watsonx.ai switched on, same cohort and same seed:

| Measure | Rule engine | Granite |
| --- | --- | --- |
| Detection rate | 89 percent, 8 of 9 | 100 percent, 9 of 9 |
| Median cycles to detection | 2.5 | 2 |
| Top five slots on real deterioration | 83 of 145 | 90 of 145 |
| Unexplained top five slots | 5 | 5 |
| watsonx.ai calls | none | 547 attempted, 547 answered, 0 fell back |
| Model | n/a | `ibm/granite-4-h-small` |

## Checklist before you upload

- [ ] Under three minutes. Check the actual duration, do not estimate.
- [ ] At least ninety seconds of the app running on screen.
- [ ] Bob visible, and the regression story told, not just mentioned.
- [ ] watsonx.ai shown answering live, not just claimed.
- [ ] Narration throughout. No silent screen recording.
- [ ] Uploaded to YouTube as unlisted or public, never private.
- [ ] Open the link in a private browser window to confirm anyone can watch it.

## One thing that will make it stand out

Most teams will narrate a feature tour. Almost nobody will show a number that
went the wrong way and explain how they caught it. The regression story is
thirty seconds and it is the most convincing half minute in the video, because
it proves the evaluation harness is real rather than decorative. Do not cut it
to save time. Cut a feature instead.
