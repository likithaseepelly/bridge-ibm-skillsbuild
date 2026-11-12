# Written problem and solution statement

Paste into the Submissions field on the My Team page. Under 500 words.

---

**Challenge statement addressed:** Track 1, Smart Healthcare. How might we use
agentic AI to expand access to healthcare services and improve patient care?

**The problem.** Hospitals manage the stay, and they manage the follow up
visit. The four weeks in between belong to nobody. A patient goes home with new
medicines, an appointment and fifteen minutes of teaching delivered at the
bedside while they are tired and waiting for transport. Readmission risk is
scored once, on the day they leave, and never recalculated. A transitional care
nurse carrying around eighty patients inside their thirty day window gets one
callback attempt each, which usually reaches voicemail. The care team finds out
something went wrong when the patient comes back through the emergency
department. Nationally, thirty day readmissions sit near 13.9 per 100 index
admissions, only 57.5 percent of Medicare patients discharged home got primary
care follow up within thirty days in 2022, and a review of 54 studies found a
median medication error rate of 53 percent. The gap is not knowledge. It is
attention during the window.

**The solution.** Bridge is an agentic system that watches those thirty days
and answers one question every morning: which patients need a nurse today, and
why. It turns the discharge record into a plan it actively tracks. It sends short plain
language check ins timed around that plan, answerable in seconds by the patient
or a relative. It reads the replies, joins them with whether
the prescription was collected and the appointment booked, and re-ranks the cohort
each cycle on change against each patient's own baseline rather than the
population. The nurse opens one screen: five names, a one
sentence reason beside each, and the evidence trail one click away.

**Target users.** The transitional care nurse is the user. The patient and
their family caregiver are the beneficiaries, reached through her. That
direction is deliberate: a clinician stays the decision maker on every
escalation.

**Why it is different.** Outreach platforms send messages and store replies;
Bridge reads the reply, and the reply reorders the list. Risk scores are set at
discharge and expressed as a number; Bridge recalculates daily and states its
reason in a sentence a nurse can act on.
Remote monitoring needs a device and reaches a selected few; Bridge needs none
and covers the whole discharged cohort.

**Measured effect.** On a seeded synthetic cohort of sixty patients across
thirty simulated days, Bridge surfaced 8 of 9 scripted deterioration events
into the nurse's top five, a median of 2.5 cycles after the first signal. Zero
urgent replies were deferred to a later cycle, all 1,075 ranked entries carried
a reason and traceable evidence, and both injected agent failures were raised
for review rather than silently skipped.

**Boundaries.** Synthetic data only. No clinical advice, no diagnosis, no
message sent without nurse approval, and silence is never read as reassurance.
