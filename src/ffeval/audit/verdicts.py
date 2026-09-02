"""
What the auditor is allowed to say about the writer's claims.

4 Verdicts:

- SUPPORTED: The claim is supported by the packet.
- CONTRADICTED: The claim contradicts the packet.
- NOT_IN_PACKET: The claim is not in the packet.
- NOT_A_CLAIM: The text is not a claim.

This determines the faithfulness of the writer's claims to the packet and not the
truth of the claims themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

class Verdict(str, Enum):
    """The auditor's verdict on a claim."""

    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    NOT_IN_PACKET = "not_in_packet"
    NOT_A_CLAIM = "not_a_claim"

UNFAITHFUL = frozenset({Verdict.CONTRADICTED, Verdict.NOT_IN_PACKET})

@dataclass(frozen=True)
class ClaimVerdict:

    """The auditor's verdict on a claim. the claim is a string, the verdict is one of the Verdict enum values, the evidence_ids are a tuple of strings, and the reason is a string."""

    claim: str
    verdict: Verdict
    evidence_ids: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict:

        """Turning the ClaimVerdict into a JSON-ready dictionary for downstream processing."""

        return {
            "claim": self.claim,
            "verdict": self.verdict.value,
            "evidence_ids": self.evidence_ids,
            "reason": self.reason,
        }

@dataclass(frozen=True)
class AuditResult:

    """The result of an audit and the verdicts for each claim."""

    verdicts: tuple[ClaimVerdict, ...]
    model: str
    prompt_version: int

    @property
    def unfaithful(self) -> tuple[ClaimVerdict, ...]:
        """Return the unfaithful verdicts."""
        return tuple(v for v in self.verdicts if v.verdict in UNFAITHFUL)

    @property
    def unfaithful_rate(self) -> float:
        """ we're adding up the total of unfaithful claims and dividing it but the total number of claims excluding the ones that are not a claim"""
        unfaithful_count = sum(1 for v in self.verdicts if v.verdict in UNFAITHFUL)
        total_claims = len([v for v in self.verdicts if v.verdict is not Verdict.NOT_A_CLAIM])
        return unfaithful_count / total_claims if total_claims else 0
