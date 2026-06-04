"""
app/heuristics/pipeline.py
===========================
Orchestrates the full Day-3 pipeline for one assignment:

  1. Load all submissions for the assignment (with cached tokens)
  2. Generate every pair (scoped to this assignment only)
  3. Compute all heuristics for each pair
  4. Persist HeuristicScore rows (batch)
  5. Upsert FlaggedPair rows for pairs above threshold
  6. Close out the PipelineRun audit row
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from itertools import combinations
from typing import List, Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.heuristics.engine import (
    HEURISTICS,
    compute_pair,
    risk_level,
    str_to_tokens,
    tokenise,
    tokens_to_str,
)
from app.models.models import (
    Assignment,
    FlaggedPair,
    FlagStatus,
    HeuristicScore,
    PipelineRun,
    RiskLevel,
    Submission,
    TimingSignal,
)

logger = logging.getLogger(__name__)

FLAG_THRESHOLD = 0.45   # composite score to enter flagged_pairs
BATCH_SIZE     = 200    # score rows per DB flush


# ── helpers ───────────────────────────────────────────────────

def _canonical(
    a: Submission, b: Submission
) -> Tuple[Submission, Submission]:
    """Ensure sub_a.id < sub_b.id (string compare on UUID) for unique pair key."""
    return (a, b) if str(a.id) < str(b.id) else (b, a)


def _minutes_diff(
    sub_a: Submission, sub_b: Submission
) -> Optional[float]:
    if sub_a.submitted_at and sub_b.submitted_at:
        return abs(
            (sub_a.submitted_at - sub_b.submitted_at).total_seconds() / 60
        )
    return None


# ── token cache warm-up ───────────────────────────────────────

def ensure_tokens(db: Session, submission: Submission) -> List[str]:
    """
    Return (and persist if missing) the normalised token list for a submission.
    Avoids re-tokenising on every pipeline run.
    """
    if submission.token_sequence:
        return str_to_tokens(submission.token_sequence)

    tokens = tokenise(submission.raw_code)
    submission.token_sequence = tokens_to_str(tokens)
    submission.token_count    = len(tokens)
    db.add(submission)
    return tokens


# ── main pipeline ─────────────────────────────────────────────

def run_pipeline(
    db:            Session,
    assignment_id: uuid.UUID,
    triggered_by:  str = "instructor",
    threshold:     float = FLAG_THRESHOLD,
) -> PipelineRun:
    """
    Full analysis run for one assignment.
    Returns the completed PipelineRun record.
    """
    # 1. Create audit row
    run = PipelineRun(
        assignment_id   = assignment_id,
        triggered_by    = triggered_by,
        heuristics_used = [h.name for h in HEURISTICS],
        threshold       = threshold,
    )
    db.add(run)
    db.flush()   # get run.id before we reference it

    # 2. Fetch all submissions for this assignment
    submissions: List[Submission] = (
        db.execute(
            select(Submission)
            .where(Submission.assignment_id == assignment_id)
            .order_by(Submission.created_at)
        ).scalars().all()
    )

    if len(submissions) < 2:
        logger.info("run=%s: fewer than 2 submissions, nothing to compare", run.id)
        _close_run(db, run, len(submissions), 0, 0)
        return run

    # 3. Warm token cache for all submissions
    token_cache: dict[uuid.UUID, List[str]] = {}
    for sub in submissions:
        token_cache[sub.id] = ensure_tokens(db, sub)
    db.flush()

    # 4. Generate pairs & compute heuristics
    score_buffer:  List[HeuristicScore] = []
    pairs_flagged: int = 0
    n_pairs:       int = 0

    for raw_a, raw_b in combinations(submissions, 2):
        sub_a, sub_b = _canonical(raw_a, raw_b)
        n_pairs += 1

        minutes_diff = _minutes_diff(sub_a, sub_b)
        result = compute_pair(
            code_a       = sub_a.raw_code,
            code_b       = sub_b.raw_code,
            cached_tok_a = tokens_to_str(token_cache[sub_a.id]),
            cached_tok_b = tokens_to_str(token_cache[sub_b.id]),
            minutes_diff = minutes_diff,
        )

        # Accumulate individual score rows
        for h in HEURISTICS:
            score_buffer.append(HeuristicScore(
                run_id          = run.id,
                submission_a_id = sub_a.id,
                submission_b_id = sub_b.id,
                heuristic       = h.name,
                score           = result.scores[h.name],
                weight          = h.weight,
                meta            = {
                    "tok_a_len": len(token_cache[sub_a.id]),
                    "tok_b_len": len(token_cache[sub_b.id]),
                },
            ))

        # Flush score buffer in batches
        if len(score_buffer) >= BATCH_SIZE:
            db.bulk_save_objects(score_buffer)
            score_buffer.clear()

        # 5. Upsert FlaggedPair if above threshold
        if result.composite >= threshold:
            pairs_flagged += 1
            _upsert_flagged_pair(db, run, sub_a, sub_b, result)
        else:
            # Below threshold — dismiss any stale flag if it exists
            _maybe_dismiss_stale(db, sub_a.id, sub_b.id)

    # Final score flush
    if score_buffer:
        db.bulk_save_objects(score_buffer)

    # 6. Close audit row
    _close_run(db, run, len(submissions), n_pairs, pairs_flagged)
    db.commit()

    logger.info(
        "run=%s assignment=%s subs=%d pairs=%d flagged=%d",
        run.id, assignment_id, len(submissions), n_pairs, pairs_flagged,
    )
    return run


# ── upsert helpers ────────────────────────────────────────────

def _upsert_flagged_pair(
    db:     Session,
    run:    PipelineRun,
    sub_a:  Submission,
    sub_b:  Submission,
    result,
) -> None:
    existing: Optional[FlaggedPair] = db.execute(
        select(FlaggedPair).where(
            FlaggedPair.submission_a_id == sub_a.id,
            FlaggedPair.submission_b_id == sub_b.id,
        )
    ).scalar_one_or_none()

    rl = RiskLevel(risk_level(result.composite))

    if existing:
        existing.composite_score = result.composite
        existing.risk_level      = rl
        existing.score_breakdown = result.scores
        existing.timing_flag     = result.timing_flag
        existing.last_run_id     = run.id
        # Reset to pending only if previously dismissed and score rose
        if existing.status == FlagStatus.dismissed and result.composite >= 0.60:
            existing.status = FlagStatus.pending
        db.add(existing)
    else:
        db.add(FlaggedPair(
            assignment_id   = run.assignment_id,
            submission_a_id = sub_a.id,
            submission_b_id = sub_b.id,
            composite_score = result.composite,
            risk_level      = rl,
            score_breakdown = result.scores,
            timing_flag     = result.timing_flag,
            status          = FlagStatus.pending,
            last_run_id     = run.id,
        ))


def _maybe_dismiss_stale(
    db: Session,
    a_id: uuid.UUID,
    b_id: uuid.UUID,
) -> None:
    """If a pair no longer meets threshold but is still pending, auto-dismiss."""
    existing = db.execute(
        select(FlaggedPair).where(
            FlaggedPair.submission_a_id == a_id,
            FlaggedPair.submission_b_id == b_id,
            FlaggedPair.status          == FlagStatus.pending,
        )
    ).scalar_one_or_none()
    if existing:
        existing.status = FlagStatus.dismissed
        db.add(existing)


def _close_run(
    db:             Session,
    run:            PipelineRun,
    n_submissions:  int,
    n_pairs:        int,
    n_flagged:      int,
    error:          Optional[str] = None,
) -> None:
    run.submissions_count = n_submissions
    run.pairs_evaluated   = n_pairs
    run.pairs_flagged     = n_flagged
    run.finished_at       = datetime.now(timezone.utc)
    run.error             = error
    db.add(run)
