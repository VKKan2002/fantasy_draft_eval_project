# Reference labels — do not read before labelling

**If you have not yet filled in `eval/cases/2025_w03_allen.json`, stop and close this
directory.**

## What this is

An independent pass over the same 30 claims, labelled by Claude. It is **not** ground truth.
The labels in `eval/cases/` are the ground truth, because they are yours.

This exists for one purpose: after you finish your own pass, compare. Every disagreement is
worth something.

| Disagreement means | What to do |
|---|---|
| a rule in LABELLING_RULES.md is underspecified | tighten the rule, bump `rules_version`, re-label the affected claims |
| one of us misread the packet | fix that one label |
| the claim itself is genuinely ambiguous | keep both readings in the `note`, and consider cutting the claim |

Do not change your label just because this file disagrees. That defeats the point — the value
of an independent pass is entirely in its independence.

## Why the claims were written by Claude and the labels were not

Writing a claim *intended* to be contradicted and then labelling it `contradicted` is not
judgment, it is bookkeeping. You would be recording your own intent, not reading the packet.

Because the 30 sentences here arrived without labels and in mixed order, labelling them means
actually opening the packet and deciding — which is the same task the auditor performs. That
makes your labels an independent measurement rather than a restatement of what you meant to
write. Blind labelling of someone else's sentences is the stronger design, and it is also
faster for you.

## Fork settings used here

These labels assume the recommended settings from
[../LABELLING_RULES.md](../LABELLING_RULES.md): Fork 1 (a), Fork 2 (a), Fork 3 (b), Fork 4 (a).
If you settle any fork differently, some labels here will legitimately differ from yours and
that is not a disagreement worth investigating.

## Known problem found while labelling

**Claim `allen-08` exposes an interaction between the settled prose-number rule and Fork 3.**

The sentence is *"He was pressured on 34 percent of his dropbacks through the first two weeks"* —
a prose-sourced number with **no attribution**.

- The settled rule says a prose-sourced number is `supported`.
- Fork 3(b) says a news-backed claim needs attribution to be `supported`.

Both apply, and they point opposite ways. The rules are orthogonal — one is about *source type*,
the other about *attribution* — so the coherent position is that a claim must satisfy both. That
makes `allen-08` `not_in_packet` under Fork 3(b) and `supported` under Fork 3(a).

The worked example in [../../docs/DESIGN.md](../../docs/DESIGN.md) was written assuming Fork 3(a)
and says the auditor rules SUPPORTED. If you settle on 3(b), that passage needs one clause added
so it reads "...assuming the sentence attributes the figure." Worth fixing once you decide.

## Deliberately ambiguous claims

Two claims have no clean answer, and they are in the set on purpose — they are how you find out
whether your rules cover the messy middle.

- `allen-25` "Milano's absence should mean more offensive possessions for Buffalo" — an inference
  the packet does not support, or speculation that is not a claim at all?
- `allen-29` "The Bills defense has been decimated by injuries" — the packet supports *two
  defenders out*. Does "decimated" survive that, or overstate it?

If you and this file disagree on these two, the rules need a line about inference and about
intensifiers. That is a finding, not a mistake.
