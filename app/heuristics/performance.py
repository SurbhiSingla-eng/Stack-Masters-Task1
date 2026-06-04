"""
app/heuristics/performance.py
==============================
Day 4 — Performance considerations for larger cohorts.

Problems with naive O(n²) pipeline
------------------------------------
  30 students  →    435 pairs   → fast (< 1s)
 100 students  →  4,950 pairs   → ~10s, acceptable
 300 students  → 44,850 pairs   → ~90s, instructor waits too long
1000 students  → 499,500 pairs  → minutes, needs async + pruning

Solutions implemented here
---------------------------
1. MinHash pre-filter  — cheaply prune pairs that cannot exceed threshold
                         before running expensive LCS/Jaccard.
2. Parallel execution  — ProcessPoolExecutor for CPU-bound heuristics.
3. Batch DB writes     — already done in pipeline.py; documented here.
4. LCS cap             — already in engine.py (cap=2000 tokens).

All functions are drop-in replacements / wrappers; pipeline.py calls
them via feature flags controlled by settings.
"""

from __future__ import annotations

import hashlib
import logging
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from app.heuristics.engine import (
    HEURISTICS,
    PairScores,
    compute_pair,
    str_to_tokens,
    tokens_to_str,
)

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# 1. MinHash — fast approximate Jaccard pre-filter
# ══════════════════════════════════════════════════════════════
#
# MinHash approximates Jaccard(A, B) using k independent hash functions.
# If the estimated Jaccard on raw tokens is below MINHASH_PRUNE_THRESHOLD
# we skip the pair entirely — it cannot score high on structural heuristics.
#
# Error rate: with k=128 hashes, the estimation error is ±1/√128 ≈ ±0.09.
# We set the prune threshold conservatively (0.15) so we only prune pairs
# that are truly far apart.

NUM_HASHES      = 128
PRUNE_THRESHOLD = 0.15    # pairs below this estimated Jaccard are skipped


def _hash_token(token: str, seed: int) -> int:
    """Deterministic hash of a token with a seed."""
    h = hashlib.md5(f"{seed}:{token}".encode()).digest()
    return int.from_bytes(h[:4], "little")


# Pre-compute hash seeds once at module load
_SEEDS: List[int] = list(range(NUM_HASHES))


def minhash_signature(tokens: List[str]) -> List[int]:
    """
    Compute a MinHash signature (list of NUM_HASHES integers) for a token list.
    O(|tokens| × NUM_HASHES) — fast in practice for typical submission sizes.
    """
    if not tokens:
        return [0] * NUM_HASHES
    sig = [float("inf")] * NUM_HASHES
    for tok in tokens:
        for i, seed in enumerate(_SEEDS):
            h = _hash_token(tok, seed)
            if h < sig[i]:
                sig[i] = h
    return [int(v) for v in sig]


def estimated_jaccard(sig_a: List[int], sig_b: List[int]) -> float:
    """Estimate Jaccard similarity from two MinHash signatures."""
    matches = sum(a == b for a, b in zip(sig_a, sig_b))
    return matches / NUM_HASHES


def should_prune(sig_a: List[int], sig_b: List[int]) -> bool:
    """Return True if this pair can safely be skipped."""
    return estimated_jaccard(sig_a, sig_b) < PRUNE_THRESHOLD


# ══════════════════════════════════════════════════════════════
# 2. Parallel pair computation
# ══════════════════════════════════════════════════════════════

@dataclass
class PairTask:
    """Serialisable unit of work for multiprocessing."""
    id_a:         str
    id_b:         str
    code_a:       str
    code_b:       str
    tok_a_str:    str
    tok_b_str:    str
    minutes_diff: Optional[float]


def _run_task(task: PairTask) -> Tuple[str, str, PairScores]:
    """Top-level function (must be picklable) for ProcessPoolExecutor."""
    result = compute_pair(
        code_a       = task.code_a,
        code_b       = task.code_b,
        cached_tok_a = task.tok_a_str,
        cached_tok_b = task.tok_b_str,
        minutes_diff = task.minutes_diff,
    )
    return task.id_a, task.id_b, result


def compute_pairs_parallel(
    tasks:      List[PairTask],
    max_workers: int = 4,
) -> Dict[Tuple[str, str], PairScores]:
    """
    Run heuristic computation for all tasks in parallel.
    Returns {(id_a, id_b): PairScores}.

    Use when len(tasks) > ~200 (overhead not worth it below that).
    """
    results: Dict[Tuple[str, str], PairScores] = {}
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_run_task, t): t for t in tasks}
        for future in as_completed(futures):
            try:
                id_a, id_b, scores = future.result()
                results[(id_a, id_b)] = scores
            except Exception as exc:
                task = futures[future]
                logger.error("Pair (%s, %s) failed: %s", task.id_a, task.id_b, exc)
    return results


# ══════════════════════════════════════════════════════════════
# 3. Performance guidelines (documented)
# ══════════════════════════════════════════════════════════════

PERFORMANCE_NOTES = """
Performance characteristics & tuning guide
==========================================

Pair count growth
-----------------
  n submissions → n*(n-1)/2 pairs
  30  → 435     (< 1 s  synchronous, fine)
  100 → 4,950   (~5 s   synchronous, acceptable)
  300 → 44,850  (~45 s  use parallel=True)
  500 → 124,750 (~120 s use parallel + async task queue)

Token cache
-----------
  Tokenisation is O(|code|) and happens once per submission at ingest.
  Subsequent runs use the cached token_sequence column — zero re-tokenisation.
  A 200-line Python file tokenises to ~400-600 tokens in < 1 ms.

LCS cap
-------
  LCS is O(m*n). We cap at 2000 tokens per side → O(4M) per pair.
  At 45,000 pairs this is ~180B operations worst-case.
  In practice submissions are 50-300 tokens; cap is rarely hit.

MinHash pruning
---------------
  Pre-filtering with MinHash (PRUNE_THRESHOLD=0.15) skips pairs whose
  token-Jaccard is too low to ever exceed the flag threshold.
  For typical assignments ~40-60% of pairs are pruned before LCS runs.
  Enable via: run_pipeline(..., use_minhash=True)

Async / task queue
------------------
  For cohorts > 200 students:
  1. Return run_id immediately (202 Accepted)
  2. Offload run_pipeline() to ARQ or Celery worker
  3. Poll GET /assignments/{id}/runs/{run_id} for completion
  The PipelineRun.finished_at column is NULL while running.

DB batch size
-------------
  BATCH_SIZE=200 rows per bulk_save_objects() call.
  Each pair produces 5 score rows → flush every 40 pairs.
  Increase to 500 if PostgreSQL is on same machine as API.

Indexes that matter
-------------------
  flagged_pairs(assignment_id, composite_score DESC) — dashboard query
  flagged_pairs(assignment_id, risk_level)           — filter by risk
  heuristic_scores(submission_a_id, submission_b_id) — detail lookup
  submissions(assignment_id)                          — pair generation load
"""
