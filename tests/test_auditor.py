"""Tests for the deterministic half of the auditor. No model, no network."""

from pathlib import Path

import pytest

from ffeval.audit.auditor import (
    _rounds_to,
    baseline_verdict,
    build_prompt,
    parse_response,
    split_claims,
)
from ffeval.audit.evaluate import (
    always_supported_baseline,
    load_cases,
    score,
)
from ffeval.audit.packet import FactsPacket
from ffeval.audit.verdicts import UNFAITHFUL, Verdict

PACKET_PATH = Path("eval/packets/2025_w03_allen.json")
CASES_PATH = Path("eval/cases/2025_w03_allen.json")
PACKET = FactsPacket.load(PACKET_PATH)


# --------------------------------------------------------------- the scissors

def test_decimal_is_not_a_sentence_end():
    assert split_claims("He averages 25.29 points.") == ["He averages 25.29 points."]


def test_abbreviations_do_not_split():
    assert split_claims("He faces MIA. They rank No. 2 vs. QBs.") == [
        "He faces MIA.",
        "They rank No. 2 vs. QBs.",
    ]


def test_question_mark_ends_a_sentence():
    assert split_claims("Is he good? Yes.") == ["Is he good?", "Yes."]


def test_sentence_can_end_in_a_digit():
    """Counterpart to the decimal test: here the dot after a number IS a split."""
    assert split_claims("He scored 24. He rested.") == ["He scored 24.", "He rested."]


def test_bullets_are_separate_claims():
    assert split_claims("- on a bye\n- questionable") == ["- on a bye", "- questionable"]


def test_blank_lines_are_dropped():
    assert split_claims("One.\n\n\nTwo.") == ["One.", "Two."]


# ------------------------------------------------------- the number rule (Fork 1a)
# _rounds_to is private, but it encodes a decision recorded in
# eval/LABELLING_RULES.md, and a decision deserves a test.

def test_rounding_matches_at_stated_precision():
    assert _rounds_to("25", 25.29) is True       # rounds to 25
    assert _rounds_to("25.3", 25.29) is True     # rounds to 25.3
    assert _rounds_to("26", 25.29) is False


def test_non_numeric_string_does_not_crash():
    assert _rounds_to("abc", 25.29) is False


# --------------------------------------------------------------- the robot

def test_baseline_supported():
    v = baseline_verdict(PACKET, "The game total is 50.5 points.")
    assert v.verdict is Verdict.SUPPORTED
    assert v.evidence_ids, "a supported verdict must name its evidence"


def test_baseline_contradicted():
    # 99.9 is not close to any packet value at any precision.
    v = baseline_verdict(PACKET, "He averaged 99.9 points per game.")
    assert v.verdict is Verdict.CONTRADICTED


def test_baseline_abstains_without_numbers():
    """The abstention IS the baseline's weakness - pin it so it can't quietly change."""
    v = baseline_verdict(PACKET, "He looks like a solid play this week.")
    assert v.verdict is Verdict.NOT_A_CLAIM


# --------------------------------------------------------------- the scoring

def test_confusion_matrix_totals_match_claim_count():
    _, claims, _ = load_cases(CASES_PATH)
    s = score(claims, [Verdict.SUPPORTED] * len(claims))
    assert sum(s.confusion.values()) == s.n == len(claims)


def test_always_supported_floor_catches_nothing():
    """The degenerate floor has zero recall by construction."""
    _, claims, _ = load_cases(CASES_PATH)
    assert always_supported_baseline(claims).recall_unfaithful == 0.0


# --------------------------------------------------- the one that matters most

def test_baseline_still_catches_5_of_15():
    """End-to-end regression on the measured 33% recall.

    Exercises the packet loader, the number rule, the verdict logic and the scoring
    in one shot. If any of them drifts, this moves.
    """
    packet, claims, _ = load_cases(CASES_PATH)
    predicted = [baseline_verdict(packet, c.text).verdict for c in claims]
    s = score(claims, predicted)

    bad = sum(v for (t, _), v in s.confusion.items() if t in UNFAITHFUL)
    caught = sum(
        v for (t, p), v in s.confusion.items() if t in UNFAITHFUL and p in UNFAITHFUL
    )

    # Raw counts, not the ratio: 5/15 and 10/30 are both 33%.
    assert (bad, caught) == (15, 5)
    assert s.recall_unfaithful == 5 / 15


# ------------------------------------------- the LLM auditor's plumbing (no key needed)

CLAIMS = ["Buffalo is favoured by 12.5 points.", "I'd start him."]


def test_prompt_contains_packet_ids_and_numbered_claims():
    """The model can only cite ids it can see, and must know which sentence is which."""
    prompt = build_prompt(PACKET, CLAIMS)
    assert "[matchup.spread_line]" in prompt
    assert "1. Buffalo is favoured by 12.5 points." in prompt
    assert "UNTRUSTED NEWS" in prompt


def test_parse_tolerates_a_code_fence_and_row_order():
    raw = """```json
    [{"n": 2, "verdict": "not_a_claim", "evidence_ids": [], "reason": "a recommendation"},
     {"n": 1, "verdict": "supported", "evidence_ids": ["matchup.spread_line"], "reason": "ok"}]
    ```"""
    v = parse_response(raw, CLAIMS)
    assert [x.verdict for x in v] == [Verdict.SUPPORTED, Verdict.NOT_A_CLAIM]
    assert v[0].claim == CLAIMS[0], "must keep our claim text, not the model's echo"


def test_parse_raises_on_a_skipped_sentence():
    """A missing ruling is a real failure. Never backfill the majority class."""
    with pytest.raises(ValueError, match="skipped"):
        parse_response('[{"n":1,"verdict":"supported","evidence_ids":["x"],"reason":"r"}]', CLAIMS)


def test_parse_raises_on_an_unknown_verdict():
    """'unsupported' is a real thing models emit; it must not silently map to supported."""
    with pytest.raises(ValueError):
        parse_response(
            '[{"n":1,"verdict":"unsupported","evidence_ids":[],"reason":"r"},'
            ' {"n":2,"verdict":"not_a_claim","evidence_ids":[],"reason":"r"}]',
            CLAIMS,
        )


def test_render_includes_news_ids():
    """A news id the model never sees is a news id it will invent.

    Found the hard way: the first LLM run cited 'bills-coach-presser', reverse-engineered
    from a URL slug, because render() printed facts with ids and news without.
    """
    rendered = PACKET.render()
    for n in PACKET.news:
        assert f"[{n.id}]" in rendered
