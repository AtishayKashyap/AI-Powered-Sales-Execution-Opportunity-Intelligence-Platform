"""
SalesForge AI response validator.

Validation has two layers:
1. Schema validation.
2. Evidence-grounding validation.

The validator is intentionally conservative. The LLM may rewrite
the supplied facts, but it may not introduce unsupported numeric
claims or unsupported evidence statements.

Normal presentation differences are allowed, including:
- decimal -> percentage
- comma formatting
- currency formatting
- ordinary rounding
- 30/90-day time-window language
"""

import re

from .schemas import validate_explanation


NUMBER_RE = re.compile(
    r"(?<![\w.])-?\d+(?:[.,]\d+)*(?:%|K|M|â‚¹)?",
    re.IGNORECASE,
)


def _normalise_number_token(token):
    return (
        token
        .replace(",", "")
        .replace("â‚¹", "")
        .strip()
        .lower()
    )


def _evidence_strings(evidence):
    """
    Return textual representations of evidence values.

    Multiple numeric representations are included so that normal
    display formatting does not cause false grounding failures.
    """

    values = []

    for value in evidence.values():
        if value is None:
            continue

        values.append(str(value))

        if isinstance(value, bool):
            continue

        if isinstance(value, (int, float)):
            values.append(f"{value:g}")
            values.append(f"{value:.2f}")
            values.append(f"{value:.1f}")

    return values


def _numeric_evidence_values(evidence):
    """
    Extract raw numeric values from deterministic evidence.

    These raw values are used for tolerant comparison.

    Examples:

        43698.89 -> can match 43,699
        674.71   -> can match 675
        0.9846   -> can match 98.5%
        0.031    -> can match 3.1%
    """

    values = []

    for value in evidence.values():
        if isinstance(value, bool):
            continue

        if isinstance(value, (int, float)):
            values.append(float(value))

    return values


def _parse_numeric_token(token):
    """
    Convert a generated numeric token into a comparable numeric value.

    Percentages are converted to decimal form.

    Examples:

        98.5% -> 0.985
        3.1%  -> 0.031
        43699  -> 43699.0
    """

    cleaned = _normalise_number_token(token)

    is_percent = cleaned.endswith("%")

    if is_percent:
        cleaned = cleaned[:-1]

    try:
        value = float(cleaned)
    except ValueError:
        return None

    if is_percent:
        value /= 100.0

    return value


def _numeric_values_match(
    response_value,
    evidence_value,
):
    """
    Determine whether two numeric values represent the same
    underlying evidence despite normal presentation differences.

    Examples accepted:

        43698.89 -> 43699
        674.71   -> 675
        0.9846   -> 98.5%
        0.031    -> 3.1%
        0.100    -> 10.0%
    """

    if response_value is None:
        return False

    difference = abs(
        response_value - evidence_value
    )

    # Relative tolerance for floating-point / percentage
    # representation differences.
    tolerance = max(
        0.01,
        abs(evidence_value) * 0.0001,
    )

    # Allow ordinary rounding to a displayed whole number.
    if abs(evidence_value) >= 1:
        tolerance = max(
            tolerance,
            0.5,
        )

    return difference <= tolerance


def _validate_numeric_grounding(
    explanation,
    evidence,
):
    """
    Validate numeric business claims in generated prose.

    Numeric business values must be grounded in deterministic evidence.
    Time-window metadata is not itself a business claim, e.g. 30-day,
    90d, or "last 90 days". Observed durations such as "27 days since
    last order" remain subject to grounding.
    """

    haystack = " ".join(
        [
            explanation.summary,
            explanation.why_it_matters,
            explanation.recommended_action,
            *explanation.evidence_used,
        ]
    )

    evidence_values = _numeric_evidence_values(evidence)

    decline_context = bool(
        re.search(
            r"\b("
            r"declin(?:e|ed|ing)"
            r"|drop(?:ped|ping)?"
            r"|fall(?:en|ing)?"
            r"|decreas(?:e|ed|ing)"
            r"|reduc(?:e|ed|ing)"
            r"|loss|lower|down|lost"
            r")\b",
            haystack,
            flags=re.IGNORECASE,
        )
    )

    # Remove only spans that are clearly time-window metadata.
    # Replacements are applied cumulatively to cleaned_haystack.
    cleaned_haystack = haystack

    window_patterns = [
        # last 90 days / previous 30-day period / past 30d
        r"\b(?:last|past|previous|prior)\s+\d+\s*[-]?\s*"
        r"(?:d|days?|day|m|months?|month|y|years?|year)"
        r"(?:\s*[- ]?\s*(?:period|window|lookback|analysis))?\b",

        # (90d) / (30 days)
        r"\(\s*\d+\s*(?:d|days?|day|m|months?|month|y|years?|year)\s*\)",

        # 30-day revenue / 90-day assortment / 30-day period
        r"\b\d+\s*[-]\s*(?:d|days?|day|m|months?|month|y|years?|year)\s+"
        r"(?:revenue|orders?|sales|data|history|period|window|assortment|"
        r"lookback|analysis|metrics?|features?|demand|inventory|stock|"
        r"activity|performance)\b",

        # 30d revenue / 90d assortment
        r"\b\d+\s*(?:d|days?|day|m|months?|month|y|years?|year)\s+"
        r"(?:revenue|orders?|sales|data|history|period|window|assortment|"
        r"lookback|analysis|metrics?|features?|demand|inventory|stock|"
        r"activity|performance)\b",
    ]

    for pattern in window_patterns:
        cleaned_haystack = re.sub(
            pattern,
            "",
            cleaned_haystack,
            flags=re.IGNORECASE,
        )

    response_tokens = NUMBER_RE.findall(cleaned_haystack)
    missing_numbers = []

    for token in response_tokens:
        response_value = _parse_numeric_token(token)
        if response_value is None:
            continue

        normalised_token = (
            token.replace(",", "").replace("%", "").strip().lower()
        )

        # Small ordinal/count references are handled by the evidence
        # trail/textual grounding layer rather than numeric matching.
        if normalised_token in {
            "1", "2", "3", "4", "5",
            "6", "7", "8", "9", "10",
        }:
            continue

        grounded = False

        for evidence_value in evidence_values:
            if _numeric_values_match(response_value, evidence_value):
                grounded = True
                break

            # Negative growth can be presented as a positive percentage
            # when the surrounding prose explicitly describes a decline.
            if (
                decline_context
                and evidence_value < 0
                and response_value >= 0
                and _numeric_values_match(
                    abs(response_value), abs(evidence_value)
                )
            ):
                grounded = True
                break

        if not grounded:
            missing_numbers.append(token)

    if missing_numbers:
        raise ValueError(
            "Ungrounded numeric claims detected: "
            + ", ".join(sorted(set(missing_numbers)))
        )

def _validate_evidence_used(
    explanation,
    evidence,
):
    """
    Validate evidence_used as an audit trail.

    A generated evidence item must contain at least one value
    that can be grounded to the supplied deterministic evidence.

    Text values must match directly.

    Numeric values may use normal presentation differences such as:

        1879      -> 1,879
        0.031     -> 3.1%
        43698.89  -> 43,699
    """

    evidence_text_values = [
        str(value).strip().lower()
        for value in evidence.values()
        if value is not None
        and not isinstance(value, (int, float, bool))
    ]

    evidence_numeric_values = _numeric_evidence_values(
        evidence
    )

    for item in explanation.evidence_used:
        if not isinstance(item, str):
            raise ValueError(
                "Every evidence_used item must be a string"
            )

        item_lower = item.strip().lower()

        if not item_lower:
            raise ValueError(
                "evidence_used cannot contain empty strings"
            )

        # --------------------------------------------------------
        # Direct textual grounding.
        # --------------------------------------------------------

        text_grounded = any(
            value in item_lower
            for value in evidence_text_values
        )

        if text_grounded:
            continue

        # --------------------------------------------------------
        # Numeric grounding.
        #
        # This handles:
        #
        #   "Territory category orders: 1,879"
        #
        # against:
        #
        #   territory_category_orders_90d = 1879
        # --------------------------------------------------------

        item_tokens = NUMBER_RE.findall(item)

        numeric_grounded = False

        for token in item_tokens:
            # Ignore time-window references.
            if re.fullmatch(
                r"\d+\s*(?:d|days?|day|m|months?|month|y|years?|year)",
                token,
                flags=re.IGNORECASE,
            ):
                continue

            response_value = _parse_numeric_token(
                token
            )

            if response_value is None:
                continue

            if any(
                _numeric_values_match(
                    response_value,
                    evidence_value,
                )
                for evidence_value in evidence_numeric_values
            ):
                numeric_grounded = True
                break

        if numeric_grounded:
            continue

        raise ValueError(
            f"Ungrounded evidence_used item: {item}"
        )


def validate_grounding(
    payload,
    evidence,
):
    """
    Validate an LLM explanation against deterministic evidence.

    Returns:
        Explanation object if validation succeeds.

    Raises:
        ValueError if schema or grounding checks fail.
    """

    if not isinstance(evidence, dict):
        raise ValueError(
            "Evidence must be a dictionary"
        )

    explanation = validate_explanation(
        payload
    )

    _validate_numeric_grounding(
        explanation,
        evidence,
    )

    _validate_evidence_used(
        explanation,
        evidence,
    )

    return explanation