"""
app/api/routes.py
==================
All REST endpoints for the Signal Panel.

Base path: /api/v1

Assignments    POST   /assignments
               GET    /assignments/{id}

Submissions    POST   /assignments/{id}/submissions
               GET    /assignments/{id}/submissions

Pipeline       POST   /assignments/{id}/runs          ← triggers analysis
               GET    /assignments/{id}/runs/{run_id}

Results        GET    /assignments/{id}/flagged-pairs
               PATCH  /assignments/{id}/flagged-pairs/{pair_id}
               GET    /assignments/{id}/matrix         ← dashboard heatmap data
               GET    /assignments/{id}/scores          ← per-pair heuristic detail
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.heuristics.pipeline import run_pipeline
from app.models.models import (
    Assignment, FlaggedPair, FlagStatus, HeuristicScore,
    PipelineRun, RiskLevel, Submission,
)
from app.schemas.schemas import (
    AssignmentCreate, AssignmentResponse,
    ErrorResponse,
    FlaggedPairList, FlaggedPairResponse,
    HeuristicScoreResponse,
    MatrixCell, SimilarityMatrix,
    PairReview,
    RunRequest, RunResponse,
    SubmissionCreate, SubmissionResponse,
)

router = APIRouter(prefix="/api/v1")


# ── dependency ────────────────────────────────────────────────

def _get_assignment(assignment_id: uuid.UUID, db: Session) -> Assignment:
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return a


def _get_pair(pair_id: int, assignment_id: uuid.UUID, db: Session) -> FlaggedPair:
    fp = db.execute(
        select(FlaggedPair).where(
            FlaggedPair.id == pair_id,
            FlaggedPair.assignment_id == assignment_id,
        )
    ).scalar_one_or_none()
    if not fp:
        raise HTTPException(status_code=404, detail="Flagged pair not found")
    return fp


# ══════════════════════════════════════════════════════════════
# Assignments
# ══════════════════════════════════════════════════════════════

@router.post(
    "/assignments",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Assignments"],
    summary="Create an assignment",
)
def create_assignment(body: AssignmentCreate, db: Session = Depends(get_db)):
    a = Assignment(**body.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@router.get(
    "/assignments/{assignment_id}",
    response_model=AssignmentResponse,
    tags=["Assignments"],
    summary="Get assignment details",
)
def get_assignment(assignment_id: uuid.UUID, db: Session = Depends(get_db)):
    return _get_assignment(assignment_id, db)


# ══════════════════════════════════════════════════════════════
# Submissions
# ══════════════════════════════════════════════════════════════

@router.post(
    "/assignments/{assignment_id}/submissions",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Submissions"],
    summary="Ingest a student submission",
    description=(
        "Creates or updates a submission for the given student. "
        "Idempotent on (assignment_id, student_id). "
        "Tokens are computed and cached on ingest."
    ),
)
def create_submission(
    assignment_id: uuid.UUID,
    body: SubmissionCreate,
    db:   Session = Depends(get_db),
):
    _get_assignment(assignment_id, db)

    from app.heuristics.engine import tokenise, tokens_to_str
    tokens = tokenise(body.raw_code)

    # Upsert on (assignment_id, student_id)
    existing = db.execute(
        select(Submission).where(
            Submission.assignment_id == assignment_id,
            Submission.student_id   == body.student_id,
        )
    ).scalar_one_or_none()

    if existing:
        existing.raw_code       = body.raw_code
        existing.student_label  = body.student_label or existing.student_label
        existing.submitted_at   = body.submitted_at  or existing.submitted_at
        existing.token_sequence = tokens_to_str(tokens)
        existing.token_count    = len(tokens)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    sub = Submission(
        assignment_id  = assignment_id,
        student_id     = body.student_id,
        student_label  = body.student_label,
        raw_code       = body.raw_code,
        token_sequence = tokens_to_str(tokens),
        token_count    = len(tokens),
        submitted_at   = body.submitted_at,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.get(
    "/assignments/{assignment_id}/submissions",
    response_model=List[SubmissionResponse],
    tags=["Submissions"],
    summary="List all submissions for an assignment",
)
def list_submissions(
    assignment_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    _get_assignment(assignment_id, db)
    subs = db.execute(
        select(Submission)
        .where(Submission.assignment_id == assignment_id)
        .order_by(Submission.created_at)
    ).scalars().all()
    return subs


# ══════════════════════════════════════════════════════════════
# Pipeline
# ══════════════════════════════════════════════════════════════

@router.post(
    "/assignments/{assignment_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Pipeline"],
    summary="Trigger a similarity analysis run",
    description=(
        "Runs all heuristics across every submission pair for this assignment. "
        "Upserts FlaggedPair rows and writes an audit PipelineRun record. "
        "Synchronous for now; wrap in a task queue (Celery/ARQ) for large cohorts."
    ),
)
def trigger_run(
    assignment_id: uuid.UUID,
    body: RunRequest = RunRequest(),
    db:   Session   = Depends(get_db),
):
    _get_assignment(assignment_id, db)
    try:
        run = run_pipeline(
            db            = db,
            assignment_id = assignment_id,
            triggered_by  = "instructor",
            threshold     = body.threshold,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return run


@router.get(
    "/assignments/{assignment_id}/runs/{run_id}",
    response_model=RunResponse,
    tags=["Pipeline"],
    summary="Get pipeline run status",
)
def get_run(
    assignment_id: uuid.UUID,
    run_id:        uuid.UUID,
    db:            Session = Depends(get_db),
):
    run = db.execute(
        select(PipelineRun).where(
            PipelineRun.id            == run_id,
            PipelineRun.assignment_id == assignment_id,
        )
    ).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return run


# ══════════════════════════════════════════════════════════════
# Flagged pairs
# ══════════════════════════════════════════════════════════════

@router.get(
    "/assignments/{assignment_id}/flagged-pairs",
    response_model=FlaggedPairList,
    tags=["Results"],
    summary="List flagged pairs for the dashboard",
)
def list_flagged_pairs(
    assignment_id: uuid.UUID,
    risk_level:    Optional[str] = Query(None, pattern="^(low|medium|high|critical)$"),
    status:        Optional[str] = Query(None, pattern="^(pending|reviewing|confirmed|dismissed|escalated)$"),
    min_score:     Optional[float] = Query(None, ge=0.0, le=1.0),
    page:          int = Query(1, ge=1),
    page_size:     int = Query(20, ge=1, le=100),
    db:            Session = Depends(get_db),
):
    _get_assignment(assignment_id, db)

    q = (
        select(FlaggedPair)
        .options(
            joinedload(FlaggedPair.submission_a),
            joinedload(FlaggedPair.submission_b),
        )
        .where(FlaggedPair.assignment_id == assignment_id)
    )

    if risk_level:
        q = q.where(FlaggedPair.risk_level == RiskLevel(risk_level))
    if status:
        q = q.where(FlaggedPair.status == FlagStatus(status))
    if min_score is not None:
        q = q.where(FlaggedPair.composite_score >= min_score)

    total = db.execute(
        select(func.count()).select_from(q.subquery())
    ).scalar_one()

    items = db.execute(
        q.order_by(FlaggedPair.composite_score.desc())
         .offset((page - 1) * page_size)
         .limit(page_size)
    ).scalars().all()

    return FlaggedPairList(total=total, page=page, items=items)


@router.patch(
    "/assignments/{assignment_id}/flagged-pairs/{pair_id}",
    response_model=FlaggedPairResponse,
    tags=["Results"],
    summary="Review a flagged pair (confirm / dismiss / escalate)",
)
def review_pair(
    assignment_id: uuid.UUID,
    pair_id:       int,
    body:          PairReview,
    db:            Session = Depends(get_db),
):
    from datetime import datetime, timezone
    fp = _get_pair(pair_id, assignment_id, db)
    fp.status          = FlagStatus(body.status)
    fp.instructor_note = body.instructor_note
    fp.reviewed_at     = datetime.now(timezone.utc)
    db.commit()
    db.refresh(fp)
    return fp


# ══════════════════════════════════════════════════════════════
# Similarity matrix (heatmap data for dashboard)
# ══════════════════════════════════════════════════════════════

@router.get(
    "/assignments/{assignment_id}/matrix",
    response_model=SimilarityMatrix,
    tags=["Results"],
    summary="Similarity matrix — powers the heatmap UI",
    description=(
        "Returns the upper-triangle similarity matrix for all submission pairs. "
        "Includes composite score and risk level for every pair. "
        "Pairs not yet analysed are omitted."
    ),
)
def get_matrix(
    assignment_id: uuid.UUID,
    db:            Session = Depends(get_db),
):
    _get_assignment(assignment_id, db)

    pairs = db.execute(
        select(FlaggedPair)
        .options(
            joinedload(FlaggedPair.submission_a),
            joinedload(FlaggedPair.submission_b),
        )
        .where(FlaggedPair.assignment_id == assignment_id)
    ).scalars().all()

    # Collect ordered student list
    seen: dict[uuid.UUID, str] = {}
    for fp in pairs:
        for sub in (fp.submission_a, fp.submission_b):
            if sub.id not in seen:
                seen[sub.id] = sub.student_label or sub.student_id

    students = list(seen.values())

    cells = [
        MatrixCell(
            student_a_label = fp.submission_a.student_label or fp.submission_a.student_id,
            student_b_label = fp.submission_b.student_label or fp.submission_b.student_id,
            composite_score = fp.composite_score,
            risk_level      = fp.risk_level.value,
            flagged_pair_id = fp.id,
        )
        for fp in pairs
    ]

    return SimilarityMatrix(
        assignment_id = assignment_id,
        students      = students,
        cells         = cells,
    )


# ══════════════════════════════════════════════════════════════
# Per-pair heuristic detail
# ══════════════════════════════════════════════════════════════

@router.get(
    "/assignments/{assignment_id}/scores",
    response_model=List[HeuristicScoreResponse],
    tags=["Results"],
    summary="Per-heuristic scores for a specific submission pair",
)
def get_scores(
    assignment_id:  uuid.UUID,
    submission_a_id: uuid.UUID = Query(...),
    submission_b_id: uuid.UUID = Query(...),
    db:              Session   = Depends(get_db),
):
    # Canonicalise order
    a_id, b_id = (
        (submission_a_id, submission_b_id)
        if str(submission_a_id) < str(submission_b_id)
        else (submission_b_id, submission_a_id)
    )
    scores = db.execute(
        select(HeuristicScore)
        .where(
            HeuristicScore.submission_a_id == a_id,
            HeuristicScore.submission_b_id == b_id,
        )
        .order_by(HeuristicScore.computed_at.desc(), HeuristicScore.heuristic)
    ).scalars().all()
    return scores
