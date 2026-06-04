"""
app/heuristics/explainer.py
============================
Day 5 — "Why flagged" explainability layer.

Given a flagged pair, produces:
  - A plain-English summary an instructor can read
  - Per-heuristic verdicts with severity labels
  - Extracted evidence: the actual shared token n-grams
  - A structured ExplanationReport used by the API

Design: pure functions, no DB access, no ML.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.heuristics.engine import (
    HEURISTICS,
    HEURISTIC_MAP,
    _ngrams,
    _lcs_length,
    str_to_tokens,
    tokenise,
)


# ══════════════════════════════════════════════════════════════
# Thresholds for per-heuristic verdict labels
# ══════════════════════════════════════════════════════════════

_VERDICT_THRESHOLDS = [
    (0.80, "very high",  "strong indicator of copying"),
    (0.60, "high",       "significant overlap"),
    (0.40, "moderate",   "notable similarity"),
    (0.20, "low",        "minor overlap"),
    (0.00, "negligible", "within normal range"),
]

def _verdict(score: float) -> Tuple[str, str]:
    """Return (severity_label, description) for a single heuristic score."""
    for threshold, label, desc in _VERDICT_THRESHOLDS:
        if score >= threshold:
            return label, desc
    return "negligible", "within normal range"


# ══════════════════════════════════════════════════════════════
# Evidence extraction
# ══════════════════════════════════════════════════════════════

def _shared_ngram_phrases(
    tok_a: List[str],
    tok_b: List[str],
    n: int = 5,
    max_phrases: int = 8,
) -> List[str]:
    """
    Return up to max_phrases of the longest shared n-gram token sequences.
    These are shown to the instructor as concrete evidence.
    """
    sa = _ngrams(tok_a, n)
    sb = _ngrams(tok_b, n)
    shared = sa & sb
    # Sort by length (all same n here) then lexicographically for stability
    phrases = sorted(shared)[:max_phrases]
    # Convert pipe-separated internal format back to readable tokens
    return [p.replace("|", " ") for p in phrases]


def _lcs_token_sequence(
    tok_a: List[str],
    tok_b: List[str],
    cap: int = 300,
) -> List[str]:
    """
    Recover the actual LCS token sequence (not just its length).
    Capped for performance. Used as the primary evidence snippet.
    """
    a, b = tok_a[:cap], tok_b[:cap]
    m, n = len(a), len(b)
    # Build full DP table (needed for backtracking)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i-1] == b[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])

    # Backtrack
    seq: List[str] = []
    i, j = m, n
    while i > 0 and j > 0:
        if a[i-1] == b[j-1]:
            seq.append(a[i-1])
            i -= 1
            j -= 1
        elif dp[i-1][j] > dp[i][j-1]:
            i -= 1
        else:
            j -= 1
    return list(reversed(seq))


# ══════════════════════════════════════════════════════════════
# Report dataclasses
# ══════════════════════════════════════════════════════════════

@dataclass
class HeuristicVerdict:
    heuristic:   str
    description: str          # human-readable heuristic name
    score:       float
    weight:      float
    severity:    str          # "very high" | "high" | "moderate" | "low" | "negligible"
    finding:     str          # one-line explanation
    contributed: bool         # True if this heuristic is meaningfully above noise


@dataclass
class EvidenceSnippet:
    kind:    str              # "shared_ngrams" | "lcs_sequence"
    tokens:  List[str]
    note:    str


@dataclass
class ExplanationReport:
    composite_score:   float
    risk_level:        str
    timing_flag:       bool

    summary:           str              # plain-English paragraph for instructors
    primary_signal:    str              # name of strongest heuristic
    heuristic_verdicts: List[HeuristicVerdict]
    evidence:          List[EvidenceSnippet]

    # Structured fields the frontend can render directly
    reasons:           List[str]        # bullet-point list of findings
    recommendation:    str              # what the instructor should do next


# ══════════════════════════════════════════════════════════════
# Plain-English generators
# ══════════════════════════════════════════════════════════════

_HEURISTIC_PLAIN: Dict[str, str] = {
    "token_jaccard_3gram":  "Short token sequence overlap (3-grams)",
    "token_jaccard_5gram":  "Longer token sequence overlap (5-grams)",
    "normalised_lcs":       "Preserved structural order (LCS)",
    "containment_5gram":    "One submission contained within the other",
    "cosine_tf":            "Overall token vocabulary similarity",
}

def _heuristic_finding(name: str, score: float, severity: str) -> str:
    templates = {
        "token_jaccard_3gram": {
            "very high": "Identical short code patterns after identifier normalisation.",
            "high":      "Most 3-token patterns are shared — consistent with copying.",
            "moderate":  "Many 3-token patterns overlap — could be a common template.",
            "low":       "Some short patterns shared — likely coincidental.",
            "negligible":"Minimal shared short patterns.",
        },
        "token_jaccard_5gram": {
            "very high": "Long phrase sequences are nearly identical — very strong copying signal.",
            "high":      "Many 5-token sequences match — hard to explain by coincidence.",
            "moderate":  "Some longer phrases overlap.",
            "low":       "Few long phrases shared.",
            "negligible":"No significant long phrase overlap.",
        },
        "normalised_lcs": {
            "very high": "Token order is almost identical — structure was preserved, not just content.",
            "high":      "Large common subsequence — logic flow is shared.",
            "moderate":  "Moderate shared subsequence — some structural similarity.",
            "low":       "Short common subsequence — normal for same-problem submissions.",
            "negligible":"Minimal shared token order.",
        },
        "containment_5gram": {
            "very high": "One submission is almost entirely contained within the other.",
            "high":      "Most of one submission's patterns appear inside the other.",
            "moderate":  "Significant portion of one submission found in the other.",
            "low":       "Small portion of one submission found in the other.",
            "negligible":"No meaningful containment detected.",
        },
        "cosine_tf": {
            "very high": "Token frequency profiles are nearly identical.",
            "high":      "Very similar token usage patterns overall.",
            "moderate":  "Token usage profiles are noticeably similar.",
            "low":       "Slightly similar token profiles.",
            "negligible":"Token profiles are distinct.",
        },
    }
    return templates.get(name, {}).get(severity, f"{severity} similarity detected.")


def _build_summary(
    verdicts: List[HeuristicVerdict],
    composite: float,
    risk: str,
    timing_flag: bool,
    label_a: str,
    label_b: str,
) -> str:
    strong = [v for v in verdicts if v.severity in ("very high", "high")]
    moderate = [v for v in verdicts if v.severity == "moderate"]

    parts = []

    if risk == "critical":
        parts.append(
            f"The submissions from {label_a} and {label_b} are extremely similar "
            f"(composite score {composite:.0%}). "
        )
    elif risk == "high":
        parts.append(
            f"The submissions from {label_a} and {label_b} show strong similarity "
            f"(composite score {composite:.0%}). "
        )
    else:
        parts.append(
            f"The submissions from {label_a} and {label_b} show moderate similarity "
            f"(composite score {composite:.0%}). "
        )

    if strong:
        names = " and ".join(v.description for v in strong[:2])
        parts.append(f"The strongest signals are {names}. ")

    if timing_flag:
        parts.append(
            "Both submissions were made within minutes of each other, "
            "which corroborates the structural similarity. "
        )

    if risk in ("critical", "high"):
        parts.append(
            "The similarity persists after stripping comments, renaming all variables, "
            "and normalising string literals — cosmetic changes would not explain this score."
        )
    else:
        parts.append(
            "This level of similarity may reflect a common approach, shared reference material, "
            "or a class template rather than copying. Manual review is recommended."
        )

    return "".join(parts)


def _build_recommendation(risk: str, timing_flag: bool) -> str:
    if risk == "critical":
        return (
            "Open both submissions side-by-side immediately. "
            "The similarity is high enough to warrant a formal review process."
        )
    if risk == "high":
        r = "Compare the submissions manually, focusing on logic structure and variable names."
        if timing_flag:
            r += " The near-simultaneous submission time strengthens the case for review."
        return r
    return (
        "Skim both submissions. Check whether the assignment provided starter code "
        "or a required structure that would explain the overlap."
    )


# ══════════════════════════════════════════════════════════════
# Main entry point
# ══════════════════════════════════════════════════════════════

def explain(
    code_a:        str,
    code_b:        str,
    score_breakdown: Dict[str, float],
    composite_score: float,
    risk_level:    str,
    timing_flag:   bool,
    label_a:       str = "Student A",
    label_b:       str = "Student B",
    cached_tok_a:  Optional[str] = None,
    cached_tok_b:  Optional[str] = None,
) -> ExplanationReport:
    """
    Build a full ExplanationReport for a flagged pair.

    Parameters
    ----------
    code_a / code_b         Raw source code strings
    score_breakdown         {heuristic_name: score} from FlaggedPair.score_breakdown
    composite_score         Weighted composite
    risk_level              "low" | "medium" | "high" | "critical"
    timing_flag             Whether submissions were near-simultaneous
    label_a / label_b       Student display labels
    cached_tok_a/b          Pre-tokenised strings (optional, avoids re-tokenising)
    """
    tok_a = str_to_tokens(cached_tok_a) if cached_tok_a else tokenise(code_a)
    tok_b = str_to_tokens(cached_tok_b) if cached_tok_b else tokenise(code_b)

    # ── Per-heuristic verdicts ─────────────────────────────
    verdicts: List[HeuristicVerdict] = []
    for h in HEURISTICS:
        score    = score_breakdown.get(h.name, 0.0)
        sev, _   = _verdict(score)
        finding  = _heuristic_finding(h.name, score, sev)
        verdicts.append(HeuristicVerdict(
            heuristic   = h.name,
            description = _HEURISTIC_PLAIN.get(h.name, h.description),
            score       = score,
            weight      = h.weight,
            severity    = sev,
            finding     = finding,
            contributed = score >= 0.20,
        ))

    verdicts.sort(key=lambda v: v.score, reverse=True)
    primary_signal = verdicts[0].heuristic if verdicts else "unknown"

    # ── Evidence ───────────────────────────────────────────
    evidence: List[EvidenceSnippet] = []

    # Shared 5-grams (most readable concrete evidence)
    shared_phrases = _shared_ngram_phrases(tok_a, tok_b, n=5, max_phrases=6)
    if shared_phrases:
        evidence.append(EvidenceSnippet(
            kind   = "shared_ngrams",
            tokens = shared_phrases,
            note   = (
                f"{len(shared_phrases)} shared 5-token sequences found after "
                "identifier normalisation. These patterns appear in both submissions."
            ),
        ))

    # LCS token sequence (structural evidence)
    lcs_seq = _lcs_token_sequence(tok_a, tok_b, cap=300)
    if len(lcs_seq) >= 10:
        evidence.append(EvidenceSnippet(
            kind   = "lcs_sequence",
            tokens = lcs_seq[:40],   # cap display at 40 tokens
            note   = (
                f"Longest common token subsequence is {len(lcs_seq)} tokens. "
                "This is the shared structural backbone visible in both submissions."
            ),
        ))

    # ── Reasons (bullet points) ────────────────────────────
    reasons: List[str] = []
    for v in verdicts:
        if v.contributed:
            reasons.append(f"{v.description}: {v.finding}")
    if timing_flag:
        reasons.append(
            "Submission timing: both submissions were made within minutes of each other."
        )
    if not reasons:
        reasons.append("Composite score exceeded threshold but no individual signal is dominant.")

    # ── Summary & recommendation ───────────────────────────
    summary = _build_summary(
        verdicts, composite_score, risk_level, timing_flag, label_a, label_b
    )
    recommendation = _build_recommendation(risk_level, timing_flag)

    return ExplanationReport(
        composite_score    = composite_score,
        risk_level         = risk_level,
        timing_flag        = timing_flag,
        summary            = summary,
        primary_signal     = primary_signal,
        heuristic_verdicts = verdicts,
        evidence           = evidence,
        reasons            = reasons,
        recommendation     = recommendation,
    )
