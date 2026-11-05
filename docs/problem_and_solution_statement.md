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
department. Nationally the thirty day all cause readmission rate has sat near
13.9 per 100 index admissions, only 57.5 percent of Medicare patients
discharged home received primary care follow up within thirty days in 2022, and
a review of 54 studies found a median medication error rate of 53 percent. The gap is not knowledge. It is attention during the window.

**The solution.** Bridge is an agentic system that watches those thirty days
and answers one question every morning: which patients need a nurse today, and
why. It turns the discharge record into a plan it actively tracks. It sends
short plain language check ins timed around that plan, which a patient or a
relative can answer in seconds. It reads the replies, joins them with whether
the prescription was collected and the appointment booked, and re-ranks the
whole cohort each cycle on change against each patient's own baseline rather
than against the population. The nurse opens one screen: five names, a one
sentence reason beside each, and the evidence trail one click away.

**Target users.** The transitional care nurse is the user. The patient and
their family caregiver are the beneficiaries, reached through her. That
direction is deliberate. A clinician stays the decision maker on every
escalation.

**Why it is different.** Outreach platforms send messages and store the
replies; Bridge reads the reply and the reply changes the order of the list.
Risk scores are calculated at discharge and expressed as a number; Bridge
recalculates daily and states its reason in a sentence a nurse can act on.
Remote monitoring needs a device and reaches a selected few; Bridge needs none
and covers the whole discharged cohort.

**Measured effect.** On a seeded synthetic cohort of sixty patients across
thirty simulated days, Bridge surfaced 8 of 9 scripted deterioration events
into the nurse's top five, with a median of one cycle between the first signal
and the case being raised. Zero urgent replies were ever deferred to a later
cycle, every ranked entry carried a reason and traceable evidence, and injected
agent failures were raised for manual review rather than silently skipped.

**Boundaries.** Synthetic data only. No clinical advice, no diagnosis, no
message sent without nurse approval, and silence is never read as reassurance.
