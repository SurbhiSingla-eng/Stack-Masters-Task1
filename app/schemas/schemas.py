"""
app/schemas/schemas.py
=======================
Pydantic v2 schemas — the API contract layer.
These are the shapes the REST API accepts and returns.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ══════════════════════════════════════════════════════════════
# Shared
# ══════════════════════════════════════════════════════════════

class OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ══════════════════════════════════════════════════════════════
# Assignment
# ══════════════════════════════════════════════════════════════

class AssignmentCreate(BaseModel):
    lms_id:    Optional[str]  = None
    course_id: str            = Field(..., min_length=1)
    title:     str            = Field(..., min_length=1, max_length=512)
    language:  str            = Field(default="unknown")
    due_at:    Optional[datetime] = None


class AssignmentResponse(OrmBase):
    id:         UUID
    lms_id:     Optional[str]
    course_id:  str
    title:      str
    language:   str
    due_at:     Optional[datetime]
    created_at: datetime


# ══════════════════════════════════════════════════════════════
# Submission
# ══════════════════════════════════════════════════════════════

class SubmissionCreate(BaseModel):
    student_id:    str  = Field(..., min_length=1, max_length=255)
    student_label: Optional[str] = Field(None, max_length=100)
    raw_code:      str  = Field(..., min_length=1)
    submitted_at:  Optional[datetime] = None

    @field_validator("raw_code")
    @classmethod
    def code_not_whitespace_only(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("raw_code must contain non-whitespace content")
        return v


class SubmissionResponse(OrmBase):
    id:            UUID
    assignment_id: UUID
    student_id:    str
    student_label: Optional[str]
    token_count:   Optional[int]
    submitted_at:  Optional[datetime]
    created_at:    datetime


# ══════════════════════════════════════════════════════════════
# Pipeline run
# ══════════════════════════════════════════════════════════════

class RunRequest(BaseModel):
    threshold: float = Field(
        default=0.45, ge=0.0, le=1.0,
        description="Composite score above which a pair is flagged"
    )


class RunResponse(OrmBase):
    id:                UUID
    assignment_id:     UUID
    triggered_by:      str
    heuristics_used:   List[str]
    threshold:         float
    submissions_count: int
    pairs_evaluated:   int
    pairs_flagged:     int
    started_at:        datetime
    finished_at:       Optional[datetime]
    error:             Optional[str]


# ══════════════════════════════════════════════════════════════
# Heuristic scores
# ══════════════════════════════════════════════════════════════

class HeuristicScoreResponse(OrmBase):
    heuristic:   str
    score:       float
    weight:      float
    computed_at: datetime


# ══════════════════════════════════════════════════════════════
# Flagged pairs
# ══════════════════════════════════════════════════════════════

class SubmissionSnippet(OrmBase):
    id:            UUID
    student_id:    str
    student_label: Optional[str]


class FlaggedPairResponse(OrmBase):
    id:              int
    assignment_id:   UUID
    composite_score: float
    risk_level:      str
    score_breakdown: Dict[str, float]
    timing_flag:     bool
    status:          str
    flagged_at:      datetime
    reviewed_at:     Optional[datetime]
    instructor_note: Optional[str]
    submission_a:    SubmissionSnippet
    submission_b:    SubmissionSnippet


class FlaggedPairList(BaseModel):
    total: int
    page:  int
    items: List[FlaggedPairResponse]


class PairReview(BaseModel):
    status:          str = Field(..., pattern="^(reviewing|confirmed|dismissed|escalated)$")
    instructor_note: Optional[str] = Field(None, max_length=2000)


# ══════════════════════════════════════════════════════════════
# Similarity matrix (dashboard view)
# ══════════════════════════════════════════════════════════════

class MatrixCell(BaseModel):
    student_a_label: str
    student_b_label: str
    composite_score: float
    risk_level:      str
    flagged_pair_id: Optional[int]


class SimilarityMatrix(BaseModel):
    assignment_id: UUID
    students:      List[str]          # ordered label list
    cells:         List[MatrixCell]   # upper triangle only


# ══════════════════════════════════════════════════════════════
# Error
# ══════════════════════════════════════════════════════════════

class ErrorResponse(BaseModel):
    code:    str
    message: str
    detail:  Optional[Any] = None
