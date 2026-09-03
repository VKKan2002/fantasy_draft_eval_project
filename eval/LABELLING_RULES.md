# Labelling rules

Read this before labelling anything. Its whole purpose is that you give the same sentence the
same verdict on Tuesday and on Thursday — without it, the labels drift, and the labels are the
ground truth every auditor score is measured against.

`rules_version` in each case file records which version of this document produced its labels.
**Bump it whenever anything below changes**, because comparing scores across a rules change is
the quiet way to invent an improvement.

---

## The question you are answering

For each sentence: **does this follow from the packet it was given?**

Not "is it true." Not "would a fantasy manager find it useful." Not "is it well written."
"Buffalo plays in the AFC East" is true and gets `not_in_packet`, because the packet does not
contain it. That distinction is the whole reason this is measurable at all — truth about the
world takes a season to arrive, faithfulness to a packet takes ten seconds.

## The four verdicts

| Verdict | Use when |
|---|---|
| `supported` | the packet contains this, and you can name the fact or news id that does it |
| `contradicted` | the packet says something incompatible with this |
| `not_in_packet` | the packet neither confirms nor denies it — including true things it omits |
| `not_a_claim` | there is no factual assertion to check |

Every `supported` label needs at least one entry in `evidence_ids`. If you cannot name the
evidence, it is not supported — that rule exists because "it seems right" is exactly the
judgment the auditor is not allowed to make either.

---

## Settled

**Prose-sourced numbers are `supported`.** A sentence repeating a figure that appears only in a
news snippet is faithful — the number is in the packet. Whether a number is *allowed* to rest on
prose is a separate policy question, enforced by a deterministic gate outside the auditor. See
the design rule in [../docs/DESIGN.md](../docs/DESIGN.md). Label faithfulness only.

---

## Forks you must settle before labelling

Each of these will come up in the first ten sentences. Pick one option, delete the other, and
write the date you decided.

### Fork 1 — numeric tolerance

A sentence says "averaged 25 points"; the packet says 25.29.

- **(a)** Supported if the stated number rounds to the packet value at the precision the
  sentence uses. "25" rounds from 25.29, so supported. "25.3" also supported. "26" is not.
- **(b)** Supported if within a fixed absolute tolerance of ±0.5, regardless of precision.

*Recommendation: (a).* It matches how people actually write and needs no magic constant. But
(b) is easier to state inside a prompt, which matters later.

**Decided:** a  **Date:** 9/3/2026

### Fork 2 — an old news item versus a current structured fact

`injury.practice_status` is `none` for week 3 of 2025. A news snippet dated 2023 says the player
was limited in practice on Wednesday. A sentence says "he was limited in practice."

- **(a)** `contradicted`. The packet header names week 3 of 2025, so a bare present-tense claim
  is about that week, and the structured fact for that week says otherwise.
- **(b)** `supported`. The text is in the packet, and the sentence did not say *when*.

*Recommendation: (a).* Under (b), any stale article can back a present-tense claim, which
removes the whole point of storing `published`.

**Decided:** a  **Date:** 9/3/2026

### Fork 3 — what counts as attributed

A news-backed sentence can be written two ways:

- "The head coach said he expects a normal week." — attribution stated
- "He is expected to have a normal week." — same content, no attribution

- **(a)** Both `supported`. The packet backs the content either way.
- **(b)** Only the attributed form is `supported`; the bare form is `not_in_packet`, because a
  news snippet supports *that someone said something*, not the thing itself.

*Recommendation: (b),* narrowly. It is stricter than it looks and it is the rule that keeps a
beat writer's speculation from becoming the tool's own assertion. Expect it to generate
disagreements, which is why it has to be decided in advance.

**Decided:** b  **Date:** 9/3/2026

### Fork 4 — a sentence carrying two claims

"He averaged 25.29 points and faces the stingiest defense in the league." One half checks out,
one half is contradicted.

- **(a)** The worse verdict wins. Order of badness: `contradicted` > `not_in_packet` >
  `supported` > `not_a_claim`.
- **(b)** Split the sentence and label each half.

*Recommendation: (a).* Splitting means the claim you labelled no longer matches what
`split_claims` produced, and the labels stop lining up with the code.

**Decided:** a  **Date:** 9/3/2026

---

## Procedure

1. Settle the four forks above. Write the date.
2. Open the packet and **read it fully** before looking at any sentence.
3. Label every sentence in one sitting if you can. Fatigue drift is real and it is invisible.
4. Do **not** run the auditor first. Seeing its verdicts contaminates yours — you will agree
   with it more than you should, and the contamination is undetectable afterwards.
5. For each `supported`, write the `evidence_ids`. If naming them is hard, that is a signal.
6. Where you are genuinely unsure, label it anyway and add a `note` saying why. Those notes are
   how you find out which rule above is underspecified.

## Checking your own labels

A week later, re-label 20 of them without looking at your first pass. Your agreement with
yourself is the **ceiling on any auditor score** — if you disagree with yourself on 15%, no
auditor can be measured above 85% against you. Record that number; it belongs beside every
result you publish.

## A note on base rates

This eval set is deliberately enriched with failures — far more bad claims than a real week
would produce. That is on purpose: recall on unfaithful claims cannot be measured without
enough unfaithful claims to measure. The consequence is that **the unfaithful rate in this set
says nothing about production.** Two different numbers, two different datasets.
