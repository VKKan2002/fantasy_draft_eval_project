"""Rule on each sentence of writer output against a facts packet.

Splitting is deterministic and happens in Python, never in the model. If the model chose
the units, they would change between runs, no two runs would be comparable, and the hand
labels - which are attached to specific sentences - would stop matching anything.

Two auditors live here, and the cheap one comes first:

  baseline_verdict()  no model at all. Does every number in the sentence appear in the
                      packet? Catches fabricated digits, misses everything about meaning.
                      This is the number the LLM auditor has to beat, and it is free.

  audit()             the LLM auditor. Not built yet - outside the current scope.

Numeric rule is Fork 1(a) from eval/LABELLING_RULES.md: a stated number matches a packet
value if the packet value ROUNDS to it at the precision the sentence used. "25" matches
25.29; "25.3" matches 25.29; "26" does not.
"""

from __future__ import annotations

import re

from .packet import FactsPacket
from .verdicts import ClaimVerdict, Verdict

# Bumped whenever the LLM prompt text changes. Stored on every AuditResult so an old
# result file is never silently compared against a newer prompt.
PROMPT_VERSION = 1

# Abbreviations whose full stop is not a sentence end. Only ones followed by a capital
# letter matter - "No. 3" already survives, because a digit is not a capital.
_ABBREVIATIONS = (
    "vs", "Mr", "Mrs", "Ms", "Dr", "Jr", "Sr", "St", "Ave", "Inc", "Co",
    "approx", "etc", "e.g", "i.e", "No", "Nos", "Fig", "Sept", "Dec", "Jan",
)
_GUARD = "\x00"  # placeholder that cannot occur in real text

# A sentence ends at .!? only when followed by whitespace and something that starts a new
# sentence, or by the end of the string. This is what protects decimals for free: in
# "23.97" the dot is followed by a digit, not whitespace, so it never matches.
_SENTENCE_END = re.compile(r"""[.!?]+(?=\s+["'(\[]?[A-Z]|\s*$)""")

_NUMBER = re.compile(r"\d+(?:\.\d+)?")

# Words that make a sentence checkable even with no digits in it.
_COMPARATIVE = re.compile(
    r"\b(most|least|best|worst|highest|lowest|more|less|fewer|better|worse|"
    r"stingiest|toughest|easiest|top|bottom|first|second|third|"
    r"said|told|reported|announced|according)\b",
    re.IGNORECASE,
)


def split_claims(text: str) -> list[str]:
    """Writer prose -> one string per sentence.

    Deliberately dull. Every claim id in eval/cases/ is anchored to this function's
    output, so changing it invalidates the labels.

    Newlines split first, so a bulleted list counts as one sentence per bullet even
    without full stops.
    """
    out: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Hide abbreviation dots so the splitter cannot cut on them, then restore.
        hidden = line
        for abbr in _ABBREVIATIONS:
            hidden = re.sub(rf"\b{re.escape(abbr)}\.", f"{abbr}{_GUARD}", hidden)

        start = 0
        for m in _SENTENCE_END.finditer(hidden):
            piece = hidden[start : m.end()].strip()
            if piece:
                out.append(piece.replace(_GUARD, "."))
            start = m.end()
        tail = hidden[start:].strip()
        if tail:
            out.append(tail.replace(_GUARD, "."))
    return out


def looks_checkable(claim: str) -> bool:
    """Does this sentence contain something that could be confirmed or refuted?

    A guard rail on the writer, not a verdict. An auditor creates pressure toward vague
    prose, because vagueness is unfalsifiable and so never flagged. A run at 0%
    unfaithful where nothing is checkable is a failure, and only this rate says so.
    """
    return bool(_NUMBER.search(claim) or _COMPARATIVE.search(claim))


def _rounds_to(stated: str, packet_value: float) -> bool:
    """Fork 1(a): does packet_value round to `stated` at the precision `stated` uses?"""
    decimals = len(stated.split(".")[1]) if "." in stated else 0
    try:
        return round(packet_value, decimals) == round(float(stated), decimals)
    except ValueError:
        return False


def baseline_verdict(packet: FactsPacket, claim: str) -> ClaimVerdict:
    """The free, no-model auditor. Beat this or the LLM adds nothing.

    Known blind spots, all deliberate - they are the argument for the LLM:
      - cannot produce NOT_IN_PACKET at all
      - cannot tell subject from object, so a right-number-wrong-player claim passes
      - small integers match promiscuously. A rank of 2 in the packet means any sentence
        containing "2" looks supported. Left in rather than patched, so the confusion
        matrix shows the cost instead of hiding it.
    """
    stated = _NUMBER.findall(claim)
    if not stated:
        return ClaimVerdict(
            claim=claim,
            verdict=Verdict.NOT_A_CLAIM,
            evidence_ids=(),
            reason="no numbers in the sentence; this checker only reads numbers",
        )

    numbers = packet.numbers()
    matched: list[str] = []
    unmatched: list[str] = []
    for s in stated:
        hits = [fid for fid, val in numbers.items() if _rounds_to(s, val)]
        if hits:
            matched.extend(hits)
        else:
            unmatched.append(s)

    if unmatched:
        return ClaimVerdict(
            claim=claim,
            verdict=Verdict.CONTRADICTED,
            evidence_ids=(),
            reason=f"no packet fact rounds to {', '.join(unmatched)}",
        )
    return ClaimVerdict(
        claim=claim,
        verdict=Verdict.SUPPORTED,
        evidence_ids=tuple(dict.fromkeys(matched)),
        reason=f"every number matches a packet fact: {', '.join(dict.fromkeys(matched))}",
    )


# ------------------------------------------------------------------ LLM auditor: later
# Outside the current scope. The freeze target is a measured deterministic baseline; the
# model-based auditor comes after there is something for it to beat.

def build_prompt(packet: FactsPacket, claims: list[str]) -> str:
    raise NotImplementedError("LLM auditor not built yet - see later.md")


def parse_response(raw: str, claims: list[str]) -> tuple[ClaimVerdict, ...]:
    raise NotImplementedError("LLM auditor not built yet - see later.md")


def call_model(prompt: str, model: str, cache_dir: str | None = None) -> str:
    raise NotImplementedError("LLM auditor not built yet - see later.md")


def audit(packet: FactsPacket, text: str, model: str):
    raise NotImplementedError("LLM auditor not built yet - see later.md")
