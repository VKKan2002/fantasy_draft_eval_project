"""
Testing for the deterministic half of the app.
"""

import json
from pathlib import Path

from ffeval.audit.auditor import _rounds_to, baseline_verdict, split_claims
from ffeval.audit.packet import FactsPacket
from ffeval.audit.verdicts import UNFAITHFUL, Verdict

PACKET_PATH = Path("eval/packets/2025_w03_allen.json")
CASES_PATH = Path("eval/cases/2025_w03_allen.json")
PACKET = FactsPacket.load(PACKET_PATH)

def test_decimal_is_not_a_sentence_end():
    assert split_claims("He averages 25.29 points.") == ["He averages 25.29 points."]

def test_abbreviations_do_not_split():
    assert split_claims("He faces MIA. They rank No. 2 vs. QBs.") == ["He faces MIA.", "They rank No. 2 vs. QBs."]

def test_question_mark_ends_a_sentence():
    assert split_claims("Is he good? Yes.") == ["Is he good?","Yes."]



