"""
app/heuristics/engine.py
=========================
Code-aware similarity heuristics for the LMS signal panel.

Design principles
-----------------
- All functions take RAW code strings (tokenisation happens internally).
- Identifier normalisation is applied before every comparison so that
  renaming variables/functions does not evade detection.
- Every public function returns a float in [0.0, 1.0].
- No ML, no external models, no network calls.

Heuristics (defined in Day 1)
------------------------------
1. token_jaccard      — Jaccard index on normalised n-gram sets
2. normalised_lcs     — LCS ratio on normalised token sequences
3. containment        — Asymmetric: is A a subset of B (or vice versa)?
4. cosine_tf          — Cosine similarity on token term-frequency vectors
5. timing_proximity   — Submission-time closeness (separate, non-code signal)
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple


# ══════════════════════════════════════════════════════════════
# Tokeniser — language-aware normalisation
# ══════════════════════════════════════════════════════════════

# Reserved keywords that carry structural meaning and should NOT
# be renamed. Everything else (identifiers, user strings, numbers)
# is normalised to a placeholder.
_KEYWORDS = {
    # Python
    "if","elif","else","for","while","break","continue","return","pass",
    "def","class","import","from","as","with","try","except","finally",
    "raise","yield","lambda","and","or","not","in","is","True","False","None",
    "global","nonlocal","del","assert","async","await",
    # Java / C / C++
    "public","private","protected","static","void","int","float","double",
    "boolean","char","long","short","byte","new","this","super","extends",
    "implements","interface","abstract","final","return","throws","throw",
    "switch","case","default","do","instanceof","null","true","false",
    "package","import","class","enum","try","catch","finally",
    # JavaScript
    "var","let","const","function","=>","typeof","instanceof","undefined",
    "null","true","false","new","delete","in","of","for","while","if",
    "else","return","class","extends","import","export","default","from",
    "async","await","yield","throw","catch","finally","switch","case",
}

# Patterns applied in order to strip / replace non-structural content
_STRIP_PATTERNS = [
    (re.compile(r'/\*[\s\S]*?\*/'),        ''),     # block comments
    (re.compile(r'//[^\n]*'),              ''),     # line comments (C/JS)
    (re.compile(r'#[^\n]*'),              ''),     # line comments (Python)
    (re.compile(r'"""[\s\S]*?"""'),        'STR'),  # Python triple-quoted
    (re.compile(r"'''[\s\S]*?'''"),        'STR'),
    (re.compile(r'"[^"\n]*"'),             'STR'),  # double-quoted strings
    (re.compile(r"'[^'\n]*'"),             'STR'),  # single-quoted strings
    (re.compile(r'\b\d+\.?\d*([eE][+-]?\d+)?\b'), 'NUM'),  # numeric literals
]

_IDENT_RE = re.compile(r'\b[A-Za-z_][A-Za-z0-9_]*\b')


def tokenise(code: str) -> List[str]:
    """
    Strip comments/strings/numbers, normalise identifiers → ID,
    keywords → kept as-is, return token list.

    Example
    -------
    Input:  'def calculate(x, y):\\n    return x + y'
    Output: ['def', 'ID', 'ID', 'ID', 'return', 'ID', 'ID']
    """
    src = code
    for pattern, replacement in _STRIP_PATTERNS:
        src = pattern.sub(replacement, src)

    tokens: List[str] = []
    for raw in re.split(r'\s+|(?=[(){}\[\];,.])|(?<=[(){}\[\];,.])', src):
        tok = raw.strip()
        if not tok:
            continue
        if tok in {'STR', 'NUM'}:
            tokens.append(tok)
        elif tok in _KEYWORDS:
            tokens.append(tok)
        elif _IDENT_RE.fullmatch(tok):
            tokens.append('ID')
        elif re.fullmatch(r'[+\-*/%=<>!&|^~]+|[(){}\[\];,.]', tok):
            tokens.append(tok)
        # else: skip (whitespace artefacts, empty strings)
    return tokens


def tokens_to_str(tokens: List[str]) -> str:
    """Join token list to a single space-separated string for caching."""
    return ' '.join(tokens)


def str_to_tokens(s: str) -> List[str]:
    """Restore token list from cached string."""
    return s.split() if s else []


# ══════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════

def _ngrams(tokens: List[str], n: int) -> Set[str]:
    return {'|'.join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)}


def _jaccard(sa: Set[str], sb: Set[str]) -> float:
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    return inter / (len(sa) + len(sb) - inter)


def _lcs_length(a: List[str], b: List[str], cap: int = 2000) -> int:
    """O(m·n) DP, capped to avoid quadratic blowup on large submissions."""
    a, b = a[:cap], b[:cap]
    m, n = len(a), len(b)
    prev = [0] * (n + 1)
    for i in range(m):
        curr = [0] * (n + 1)
        for j in range(n):
            curr[j+1] = prev[j] + 1 if a[i] == b[j] else max(prev[j+1], curr[j])
        prev = curr
    return prev[n]


# ══════════════════════════════════════════════════════════════
# Heuristic functions
# ══════════════════════════════════════════════════════════════

def token_jaccard(code_a: str, code_b: str, n: int = 3,
                  tok_a: Optional[List[str]] = None,
                  tok_b: Optional[List[str]] = None) -> float:
    """
    Jaccard similarity over normalised n-gram token sets.
    n=3 balances specificity vs recall; n=5 catches longer verbatim runs.

    Survives: variable renaming, comment removal, string literal changes.
    Does NOT survive: reordering of independent blocks (use LCS for that).
    """
    ta = tok_a if tok_a is not None else tokenise(code_a)
    tb = tok_b if tok_b is not None else tokenise(code_b)
    return round(_jaccard(_ngrams(ta, n), _ngrams(tb, n)), 4)


def normalised_lcs(code_a: str, code_b: str,
                   tok_a: Optional[List[str]] = None,
                   tok_b: Optional[List[str]] = None) -> float:
    """
    LCS ratio on normalised token sequences (Sørensen–Dice style).
    Sensitive to preserved structural order even across renamed identifiers.

    Score = 2 * LCS / (len_a + len_b)
    """
    ta = tok_a if tok_a is not None else tokenise(code_a)
    tb = tok_b if tok_b is not None else tokenise(code_b)
    if not ta or not tb:
        return 0.0
    l = _lcs_length(ta, tb)
    return round(2 * l / (len(ta) + len(tb)), 4)


def containment(code_a: str, code_b: str, n: int = 5,
                tok_a: Optional[List[str]] = None,
                tok_b: Optional[List[str]] = None) -> float:
    """
    max(|ngrams(A)∩ngrams(B)| / |ngrams(A)|,
        |ngrams(A)∩ngrams(B)| / |ngrams(B)|)

    Detects when one submission is largely extracted from the other,
    even if the larger submission has extra code surrounding it.
    Returns the maximum of both directions (symmetric result).
    """
    ta = tok_a if tok_a is not None else tokenise(code_a)
    tb = tok_b if tok_b is not None else tokenise(code_b)
    sa, sb = _ngrams(ta, n), _ngrams(tb, n)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    return round(max(inter / len(sa), inter / len(sb)), 4)


def cosine_tf(code_a: str, code_b: str,
              tok_a: Optional[List[str]] = None,
              tok_b: Optional[List[str]] = None) -> float:
    """
    Cosine similarity on raw term-frequency vectors of normalised tokens.
    Length-independent; robust to one submission being longer than the other.
    """
    ta = tok_a if tok_a is not None else tokenise(code_a)
    tb = tok_b if tok_b is not None else tokenise(code_b)
    fa, fb = Counter(ta), Counter(tb)
    if not fa or not fb:
        return 0.0
    vocab = set(fa) | set(fb)
    dot = sum(fa[w] * fb[w] for w in vocab)
    mag_a = math.sqrt(sum(v * v for v in fa.values()))
    mag_b = math.sqrt(sum(v * v for v in fb.values()))
    if not mag_a or not mag_b:
        return 0.0
    return round(dot / (mag_a * mag_b), 4)


def timing_proximity(minutes_diff: float, window_minutes: float = 10.0) -> float:
    """
    Converts submission time difference to a [0,1] signal.
    Full score (1.0) if diff <= 0 min; decays linearly to 0 at window_minutes.
    This is NOT a structural signal — used as a soft corroborating flag only.
    """
    if minutes_diff < 0:
        minutes_diff = abs(minutes_diff)
    return round(max(0.0, 1.0 - minutes_diff / window_minutes), 4)


# ══════════════════════════════════════════════════════════════
# Registry & composite scorer
# ══════════════════════════════════════════════════════════════

@dataclass
class HeuristicDef:
    name:        str
    fn:          Callable
    weight:      float
    description: str


HEURISTICS: List[HeuristicDef] = [
    HeuristicDef(
        name        = "token_jaccard_3gram",
        fn          = lambda a, b, ta, tb: token_jaccard(a, b, n=3, tok_a=ta, tok_b=tb),
        weight      = 0.30,
        description = "Jaccard on normalised 3-gram token sets",
    ),
    HeuristicDef(
        name        = "token_jaccard_5gram",
        fn          = lambda a, b, ta, tb: token_jaccard(a, b, n=5, tok_a=ta, tok_b=tb),
        weight      = 0.15,
        description = "Jaccard on normalised 5-gram token sets (longer phrases)",
    ),
    HeuristicDef(
        name        = "normalised_lcs",
        fn          = lambda a, b, ta, tb: normalised_lcs(a, b, tok_a=ta, tok_b=tb),
        weight      = 0.30,
        description = "LCS ratio on normalised token sequences",
    ),
    HeuristicDef(
        name        = "containment_5gram",
        fn          = lambda a, b, ta, tb: containment(a, b, n=5, tok_a=ta, tok_b=tb),
        weight      = 0.15,
        description = "Max directional containment on 5-gram sets",
    ),
    HeuristicDef(
        name        = "cosine_tf",
        fn          = lambda a, b, ta, tb: cosine_tf(a, b, tok_a=ta, tok_b=tb),
        weight      = 0.10,
        description = "Cosine similarity on token TF vectors",
    ),
]

assert abs(sum(h.weight for h in HEURISTICS) - 1.0) < 1e-9, "Weights must sum to 1.0"

HEURISTIC_MAP: Dict[str, HeuristicDef] = {h.name: h for h in HEURISTICS}


@dataclass
class PairScores:
    scores:          Dict[str, float] = field(default_factory=dict)
    composite:       float            = 0.0
    timing_flag:     bool             = False
    timing_score:    float            = 0.0


def compute_pair(
    code_a:       str,
    code_b:       str,
    cached_tok_a: Optional[str] = None,
    cached_tok_b: Optional[str] = None,
    minutes_diff: Optional[float] = None,
) -> PairScores:
    """
    Run all registered heuristics for one submission pair.
    Accepts pre-tokenised (cached) token strings to avoid re-tokenising.
    Returns PairScores with per-heuristic breakdown and composite.
    """
    ta = str_to_tokens(cached_tok_a) if cached_tok_a else tokenise(code_a)
    tb = str_to_tokens(cached_tok_b) if cached_tok_b else tokenise(code_b)

    scores: Dict[str, float] = {}
    for h in HEURISTICS:
        scores[h.name] = h.fn(code_a, code_b, ta, tb)

    composite = round(
        sum(h.weight * scores[h.name] for h in HEURISTICS), 4
    )

    t_score = 0.0
    t_flag  = False
    if minutes_diff is not None:
        t_score = timing_proximity(minutes_diff)
        t_flag  = t_score >= 0.8   # submitted within ~2 min of each other

    return PairScores(
        scores       = scores,
        composite    = composite,
        timing_flag  = t_flag,
        timing_score = t_score,
    )


def risk_level(composite: float) -> str:
    if composite >= 0.80: return "critical"
    if composite >= 0.60: return "high"
    if composite >= 0.45: return "medium"
    return "low"
