import sys
from pathlib import Path

import pytest

# Make the repository root importable regardless of pytest/import mode.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.validate import validate_grounding


EVIDENCE = {
    "revenue_growth_30d": -0.42,
    "revenue_gap_vs_previous_30d": 1850,
    "orders_30d": 3,
}


def payload(summary, evidence_used=None):
    return {
        "summary": summary,
        "why_it_matters": "The supplied evidence shows a 42% decline and a revenue gap of 1,850.",
        "recommended_action": "Review the outlet and investigate the decline during the next field visit.",
        "evidence_used": evidence_used or [
            "Revenue growth: -42%",
            "Revenue gap: 1,850",
        ],
        "confidence": "high",
    }


def test_grounded_explanation_passes():
    result = validate_grounding(
        payload("Revenue recovery opportunity with a 42% decline."),
        EVIDENCE,
    )
    assert result.summary.startswith("Revenue recovery opportunity")


def test_unsupported_numeric_claim_is_rejected():
    with pytest.raises(ValueError, match="Ungrounded numeric claims detected"):
        validate_grounding(
            payload("Revenue recovery opportunity; recent revenue was 4,500."),
            EVIDENCE,
        )
