# Later

Parked deliberately. Nothing here gets discussed until `evaluate.py --baseline` prints a
confusion matrix. Adding to this file is free; taking something out of it is a decision.

## Exit condition for the current freeze

Steps 1–5 of the auditor: `verdicts.py`, `packet.py`, one real packet, the labelling
rules, ~55 labelled claims, `split_claims`, `baseline_verdict`, `evaluate.py --baseline`.

No LLM, no API key, no news fetching, no prompt engineering. Done when a confusion matrix
and a recall-on-unfaithful number print to the terminal.

---

## Ideas that cleared the bar but are not now

**Monday-morning check — the second measurement.** After games, ask whether a news item
that implied something ("the rookie is getting more carries") actually predicted it. Snap
counts and rush attempts are in nflverse by Tuesday. Passes all four evaluability
questions: fast ground truth, hundreds of observations a season, a beatable baseline
("assume nothing changes"), and a binary outcome rather than a 2.9-point edge. This is the
strongest parked item — it could produce a second publishable number.

**Source disagreement resolution.** Two beat writers say different things about whether a
player suits up. Step count depends on how contested the situation is, so it can't be
written in advance. "Sources disagree, here's both" is a legitimate terminal output.

**Waiver wire suggestions.** Candidate list is structured, ranking uses the existing
projection rule, so the only open-ended part is the news agent pointed at different
players. Possibly real headroom, because the 2.9-points-a-week ceiling was measured on
your own roster and says nothing about adding a player you don't own.

*Gate before building:* a variant of `checks/step1_baseline.py` where one rule adds the
best available free agent each week and one stands pat. One day of work, and it decides
whether the feature is worth a week.

**"What changed since last week."** Useful, cheap, roughly forty lines. Not agentic —
it's a diff. Build it, don't dress it up.

**The omission check.** The auditor sees only what was written, so an omitted Questionable
status produces no verdict. Needs a `must_mention` flag per fact and its own module
(`coverage.py`), not a bolt-on to the auditor. Cheap insurance now: add `"must_mention":
true` to the injury and bye facts while hand-typing packets, so retro-fitting doesn't mean
editing every file.

## Rejected, with reason

**Trade evaluation.** No ground truth, unmeasurable effect size, large build. Fails
evaluability questions 1, 2 and 4.

---

## Docs owed once the freeze lifts

- **DESIGN.md** — two new decisions to record beside the others that earned their place:
  structured facts are templated and the model only touches prose; the auditor's target is
  news-derived claims, where the hallucination risk actually lives.
- **DESIGN.md stack table** — the writer model's role narrows to news only.
- **DESIGN.md retrieval gates** — name gate via the existing alias table, date window,
  domain allowlist. Deterministic, in the fetch path, and the first line of defence
  against injection.
- **plan.md** — still stale, still describes a vector store and a tool-picking model.
- **eval case subtypes** — the numeric `off_by_*` cases lose most of their value once
  numbers are templated. Keep two as a tolerance regression check; spend the labelling
  effort on news attribution instead.
