"""Check that an explanation only states facts present in the opportunity's evidence.

What is checked:
  * evidence_used must name real evidence fields.
  * Every number in the text must equal (within rounding) a value derivable from the evidence:
    the value itself, the value as a percentage, in thousands ("22k"), or a ratio between two
    evidence values ("3x"). Number words ("five", "twice") are parsed too.
  * Units must match: a percentage claim needs a percentage-like field, a currency claim a money field.
  * Product categories may only be the one named in the evidence.
  * Numbers that only appear in field names (the 30/60/90-day windows) are allowed as time windows.

What is not checked: causal claims phrased without numbers. The prompt forbids them and the UI labels
LLM output as an explanation of the evidence, not as a finding.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field

from ..pipeline.generate import CATEGORIES
from .schema import ExplanationDraft

NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "fifteen": 15,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "ninety": 90,
    "hundred": 100,
    "twice": 2,
    "double": 2,
    "doubled": 2,
    "triple": 3,
    "tripled": 3,
    "half": 0.5,
    "halved": 0.5,
}
MULTIPLIER_WORDS = {"twice", "double", "doubled", "triple", "tripled", "half", "halved"}
CURRENCY = r"(?:₹|rs\.?|inr|rupees?)"
TOKEN = re.compile(
    rf"(?P<cur>{CURRENCY})?\s*(?P<num>\d+(?:,\d{{2,3}})*(?:\.\d+)?)\s*(?P<suffix>%|percent\b|k\b|lakh\b|x\b|×)?"
    r"|(?<!\w)(?P<word>[a-z]+)(?!\w)",
    re.IGNORECASE,
)
MONEY_HINTS = ("revenue", "value", "price", "sales")
PERCENT_HINTS = ("pct", "rate", "adoption", "change")
TOLERANCE = 0.011  # relative; covers rounding to the displayed precision


@dataclass
class GroundingResult:
    ok: bool
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Claim:
    value: float
    unit: str  # "plain" | "percent" | "money" | "multiplier"
    text: str


def extract_claims(text: str) -> list[Claim]:
    claims = []
    for m in TOKEN.finditer(text):
        if m.group("word"):
            word = m.group("word").lower()
            if word in NUMBER_WORDS:
                unit = "multiplier" if word in MULTIPLIER_WORDS else "plain"
                claims.append(Claim(float(NUMBER_WORDS[word]), unit, m.group(0)))
            continue
        number = float(m.group("num").replace(",", ""))
        suffix = (m.group("suffix") or "").lower()
        if suffix in ("%", "percent"):
            claims.append(Claim(number, "percent", m.group(0).strip()))
        elif suffix in ("x", "×"):
            claims.append(Claim(number, "multiplier", m.group(0).strip()))
        elif suffix == "k":
            claims.append(Claim(number * 1000, "money" if m.group("cur") else "plain", m.group(0).strip()))
        elif suffix == "lakh":
            claims.append(Claim(number * 100_000, "money" if m.group("cur") else "plain", m.group(0).strip()))
        else:
            claims.append(Claim(number, "money" if m.group("cur") else "plain", m.group(0).strip()))
    return claims


def _close(a: float, b: float) -> bool:
    if b == 0:
        return abs(a) < 1e-9
    return abs(a - b) / abs(b) <= TOLERANCE or abs(a - b) <= 0.051


def _numeric_evidence(evidence: dict[str, object]) -> dict[str, float]:
    return {k: float(v) for k, v in evidence.items() if isinstance(v, int | float) and not isinstance(v, bool)}


def _kind(field_name: str) -> str:
    if any(h in field_name for h in PERCENT_HINTS):
        return "percent"
    if any(h in field_name for h in MONEY_HINTS):
        return "money"
    if "days" in field_name:
        return "days"
    return "count"


def _allowed_values(evidence: dict[str, object]) -> dict[str, list[float]]:
    nums = _numeric_evidence(evidence)
    by_kind: dict[str, list[float]] = {}
    for name, value in nums.items():
        by_kind.setdefault(_kind(name), []).append(value)

    money = by_kind.get("money", [])
    percent = [abs(v) for v in by_kind.get("percent", [])]
    percent += [abs(v) * 100 for v in by_kind.get("percent", []) if 0 < abs(v) <= 1]
    plain = [abs(v) for v in nums.values()]
    # Time windows that only appear in field names, e.g. revenue_60d -> 60.
    plain += [float(w) for k in evidence for w in re.findall(r"(\d+)d\b", k)]

    # Ratios and percentage changes are only meaningful between fields of the same kind
    # (rupees with rupees, counts with counts), never e.g. days against rupees.
    ratios: list[float] = []
    for kind in ("money", "count", "days"):
        values = [v for v in by_kind.get(kind, []) if v > 0]
        for a, b in itertools.permutations(values, 2):
            ratios.append(a / b)
            percent.append(abs(a / b - 1) * 100)
    return {"plain": plain + money, "money": money, "percent": percent, "multiplier": ratios}


def _matches(claim: Claim, allowed: dict[str, list[float]]) -> bool:
    candidates = allowed[claim.unit] if claim.unit != "plain" else allowed["plain"]
    if claim.unit == "multiplier":
        return any(abs(claim.value - r) / r <= 0.1 for r in candidates if r > 0)
    return any(_close(claim.value, c) for c in candidates)


def check(draft: ExplanationDraft, evidence: dict[str, object]) -> GroundingResult:
    problems: list[str] = []

    unknown = [name for name in draft.evidence_used if name not in evidence]
    if unknown:
        problems.append(f"evidence_used names fields that do not exist: {unknown}")

    allowed = _allowed_values(evidence)
    for text in draft.text_fields:
        for claim in extract_claims(text):
            if not _matches(claim, allowed):
                problems.append(f'unsupported {claim.unit} claim "{claim.text}"')

    target = str(evidence.get("target_category", ""))
    for text in draft.text_fields:
        for category in CATEGORIES:
            if category.lower() in text.lower() and category != target:
                problems.append(f'mentions category "{category}" which is not in the evidence')

    return GroundingResult(ok=not problems, problems=sorted(set(problems)))
