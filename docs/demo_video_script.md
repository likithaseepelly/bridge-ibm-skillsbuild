# Three minute demo video, script and shot list

Hard limit is three minutes. Evaluators stop watching at three minutes. At
least ninety seconds must be the solution running on screen, and the use of
IBM Bob must be clearly shown.

Record at 1920 by 1080. One take per section is fine, cut them together.

---

## 0:00 to 0:25, the problem

**On screen:** a plain title card, then the team name, then a single line of
text as you speak.

**Say:**

> A patient leaves hospital with new medicines, an appointment, and fifteen
> minutes of teaching at the bedside. From that moment, for thirty days, nobody
> is watching. Risk was scored on the day they left and never recalculated. One
> transitional care nurse is carrying eighty of these patients, and she gets one
> callback attempt each. The care team finds out something went wrong when the
> patient comes back through the emergency department.

## 0:25 to 0:40, what we built

**On screen:** the five step loop, one line each, appearing as you say them.

**Say:**

> Bridge watches those thirty days. It turns the discharge record into a plan
> it tracks, checks in with the patient in short plain messages, reads the
> replies, and every morning it hands the nurse five names with a reason beside
> each. It ranks and raises. It never diagnoses, and it never decides anyone is
> safe.

## 0:40 to 2:20, the solution running, this is the part that counts

**Shot 1, the worklist.** Open the running app at the worklist.

> This is the nurse's morning. Sixty patients in their thirty day window, five
> names. Not ordered by discharge date. Ordered by what has happened since.

**Shot 2, read the top row out loud.** Point at the reason text.

> Top of the list reported an emergency sign. Below that, a patient who said
> their weight is up four pounds since Monday, which is worse than their own
> previous reply. Third, someone who has not answered in four days with a
> prescription still uncollected. Silence is a signal here, not reassurance.

**Shot 3, click Evidence on one patient.** Scroll the evidence trail.

> Every position opens to its evidence. What we asked, what came back, what the
> plan expected, what changed. The nurse can see exactly why this person is
> third and not thirtieth, which is the thing a risk score never tells her.

**Shot 4, the approval queue.** Click Approvals.

> Nothing reaches a patient without a nurse approving it. This is the queue.

**Shot 5, the urgent path.** Back to the worklist, point at the red banner.

> When a reply contains an emergency phrase it leaves the cycle immediately.
> Emergency guidance goes to the sender and the case is at the top of the list
> in the same cycle. Never held for tomorrow.

**Shot 6, the terminal.** Run `python3 eval/run_eval.py` and let it finish.

> We tested it. Sixty synthetic patients, nine with scripted deterioration,
> thirty simulated days. Eight of nine surfaced into the top five, median one
> cycle from the first signal. Zero urgent replies deferred. Two percent of top
> five slots unexplained. Every ranked entry carried a reason and traceable
> evidence.

## 2:20 to 2:45, IBM Bob

**On screen:** the Bob IDE, the Tasks list, then a task session summary open.

**Say:**

> IBM Bob was the build environment. Every component went through Bob as its
> own task, which is what these session summaries show. [Name the one place Bob
> genuinely changed the work, for example writing the test cases for the safety
> rules, or the refactor of the ranking function.] All five of our session
> records are in the repository.

## 2:45 to 3:00, close

**On screen:** the worklist again, then the repository URL.

**Say:**

> Synthetic data throughout, no personal information anywhere, and the whole
> thing clones and runs with one command. The nurse's job does not change. What
> changes is the quality of the decision she makes at the start of each day.

---

## Checklist before you upload

- [ ] Under three minutes. Check the actual duration.
- [ ] At least ninety seconds of the app running on screen.
- [ ] Bob is clearly visible and clearly described.
- [ ] Narration throughout, no silent screen recording.
- [ ] Uploaded to YouTube as unlisted or public, not private.
- [ ] Open the link in a private browser window to confirm anyone can watch it.
