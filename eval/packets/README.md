# Evaluation packets

Hand-built facts packets used to measure the claim auditor. Each file is one player in one
week, loaded by `FactsPacket.load()` in
[src/ffeval/audit/packet.py](../../src/ffeval/audit/packet.py).

## What is real and what is not

**The `facts` are real**, pulled from nflverse for the season and week named in the file.
Real numbers cannot be internally inconsistent, and an inconsistent packet makes some labels
genuinely unanswerable — if the weekly scores and the stored average disagree, a claim
quoting either one is both supported and contradicted.

**The `news` items are synthetic.** Every one has an `example.com` URL, which is the marker:
nothing in `news` is a real quote or a real article. Two reasons this is the right call rather
than a shortcut:

1. Faithfulness is measured *relative to the packet*, so a synthetic snippet is a perfectly
   valid piece of evidence to judge a sentence against. The auditor's question is "does this
   sentence follow from what it was given", never "is this quote real".
2. Constructing the failure modes requires precise control. A stale-citation test needs an
   item from an earlier season; a wrong-player test needs an item about a teammate. Real
   search results rarely hand you exactly that set.

Where a synthetic item states something factual — Matt Milano out with a pectoral injury —
that underlying fact does come from nflverse. Quotes use role attributions ("the head coach",
"a beat writer") rather than putting invented words in a named person's mouth.

## The news items are test infrastructure

Each item exists so that a specific adversarial claim is *constructible*. Remove one and the
corresponding test can no longer be written.

| Item | Enables |
|---|---|
| `news.01` | a faithful attributed claim, and the "supported" half of the label set |
| `news.02` | stale citation — an item from a previous season |
| `news.03` | prose-sourced number — a figure that appears nowhere in `facts` |
| `news.04` | wrong-player attribution — an item about teammates, not the subject |

## Adding a packet

Query nflverse for the real values, print them, and type them in by hand. Do not build a
packet generator — producing packets from live data is the pipeline's job, and a generator
here would couple the evaluation to code that does not exist yet.

Pick weeks that create test surface. A healthy player in an average matchup produces boring
claims. Useful variety: a Questionable or Out designation, a bye week, a genuinely bad
matchup, a player with almost no games played.
