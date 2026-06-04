"""
Data Model — Plagiarism Signal Panel (LMS)
==========================================

Entity overview
---------------
Assignment      One per coding task. Submissions are always compared WITHIN
                the same assignment — never across.

Submission      One per student per assignment. Stores the raw code and a
                normalised token sequence (cached to avoid re-tokenising).

HeuristicScore  One row per (submission_pair, heuristic). Append-only log;
                never mutated after insert.

FlaggedPair     Aggregated verdict row created/updated after every pipeline
                run. The dashboard reads this table exclusively.

PipelineRun     Audit trail. One row per analysis run triggered by an
                instructor or the scheduler.

TimingSignal    Captures submission timestamps for the timing heuristic.
                Stored separately so it stays optional.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum, Float,
    ForeignKey, Integer, JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


# ── Base ──────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Enums ─────────────────────────────────────────────────────

class RiskLevel(str, enum.Enum):
    low      = "low"
    medium   = "medium"
    high     = "high"
    critical = "critical"


class FlagStatus(str, enum.Enum):
    pending    = "pending"
    reviewing  = "reviewing"
    confirmed  = "confirmed"   # instructor confirmed as copying
    dismissed  = "dismissed"   # false positive
    escalated  = "escalated"


class Language(str, enum.Enum):
    python     = "python"
    java       = "java"
    javascript = "javascript"
    c          = "c"
    cpp        = "cpp"
    unknown    = "unknown"


# ── Assignment ────────────────────────────────────────────────

class Assignment(Base):
    """
    One coding assignment in the LMS.
    All similarity checks are scoped to a single assignment.
    """
    __tablename__ = "assignments"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lms_id         = Column(String(255), unique=True, nullable=True,
                            comment="External ID from the LMS (Canvas, Moodle, etc.)")
    course_id      = Column(String(255), nullable=False, index=True)
    title          = Column(String(512), nullable=False)
    language       = Column(Enum(Language), nullable=False, default=Language.unknown)
    due_at         = Column(DateTime(timezone=True), nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    submissions    = relationship("Submission",  back_populates="assignment", cascade="all, delete-orphan")
    pipeline_runs  = relationship("PipelineRun", back_populates="assignment", cascade="all, delete-orphan")


# ── Submission ────────────────────────────────────────────────

class Submission(Base):
    """
    One student's code submission for one assignment.
    token_sequence is the normalised, whitespace-joined token list
    computed once at ingest and cached here.
    """
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "student_id", name="uq_submission_per_student"),
    )

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id   = Column(UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    student_id      = Column(String(255), nullable=False,
                             comment="Anonymised student reference from LMS")
    student_label   = Column(String(100), nullable=True,
                             comment="Display name or alias shown in the panel")
    raw_code        = Column(Text, nullable=False)
    token_sequence  = Column(Text, nullable=True,
                             comment="Normalised token stream — cached at ingest")
    token_count     = Column(Integer, nullable=True)
    submitted_at    = Column(DateTime(timezone=True), nullable=True,
                             comment="Original LMS submission timestamp")
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    assignment      = relationship("Assignment",    back_populates="submissions")
    timing_signal   = relationship("TimingSignal",  back_populates="submission",
                                   uselist=False, cascade="all, delete-orphan")

    # pairs this submission appears in (either side)
    pairs_as_a      = relationship("FlaggedPair", foreign_keys="FlaggedPair.submission_a_id",
                                   back_populates="submission_a", cascade="all, delete-orphan")
    pairs_as_b      = relationship("FlaggedPair", foreign_keys="FlaggedPair.submission_b_id",
                                   back_populates="submission_b", cascade="all, delete-orphan")


# ── TimingSignal ──────────────────────────────────────────────

class TimingSignal(Base):
    """
    Derived timing features computed from submission timestamps.
    Used as one heuristic signal alongside structural similarity.
    """
    __tablename__ = "timing_signals"

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id         = Column(UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"),
                                   unique=True, nullable=False)
    minutes_before_due    = Column(Float, nullable=True,
                                   comment="Negative = submitted after deadline")
    percentile_in_cohort  = Column(Float, nullable=True,
                                   comment="0–1; where this submission sits in the time distribution")
    is_outlier            = Column(Boolean, nullable=False, default=False,
                                   comment="True if submitted within 5 min of another submission")

    submission            = relationship("Submission", back_populates="timing_signal")


# ── HeuristicScore ────────────────────────────────────────────

class HeuristicScore(Base):
    """
    Append-only log of individual heuristic results for a pair.
    Canonical ordering: submission_a_id < submission_b_id (UUID string sort).
    Each pipeline run inserts fresh rows — old rows are retained for audit.
    """
    __tablename__ = "heuristic_scores"

    id               = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id           = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    submission_a_id  = Column(UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"),
                              nullable=False)
    submission_b_id  = Column(UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"),
                              nullable=False)
    heuristic        = Column(String(64), nullable=False,
                              comment="e.g. token_jaccard_3gram, normalised_lcs")
    score            = Column(Float, nullable=False,
                              comment="Always in [0, 1]")
    weight           = Column(Float, nullable=False,
                              comment="Weight used in composite at time of computation")
    meta             = Column(JSON, nullable=False, default=dict,
                              comment="Heuristic-specific detail (token counts, etc.)")
    computed_at      = Column(DateTime(timezone=True), server_default=func.now())

    run              = relationship("PipelineRun", back_populates="heuristic_scores")


# ── FlaggedPair ───────────────────────────────────────────────

class FlaggedPair(Base):
    """
    One row per unique submission pair per assignment.
    Upserted after every pipeline run — always reflects the latest scores.
    This is the primary table for the instructor dashboard.
    """
    __tablename__ = "flagged_pairs"
    __table_args__ = (
        UniqueConstraint("submission_a_id", "submission_b_id", name="uq_flagged_pair"),
    )

    id                = Column(BigInteger, primary_key=True, autoincrement=True)
    assignment_id     = Column(UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    submission_a_id   = Column(UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"),
                               nullable=False)
    submission_b_id   = Column(UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"),
                               nullable=False)

    composite_score   = Column(Float, nullable=False,
                               comment="Weighted average of all heuristic scores")
    risk_level        = Column(Enum(RiskLevel), nullable=False, index=True)
    score_breakdown   = Column(JSON, nullable=False, default=dict,
                               comment="Snapshot: {heuristic: score} at last run")
    timing_flag       = Column(Boolean, nullable=False, default=False,
                               comment="True if both submissions were near-simultaneous")

    status            = Column(Enum(FlagStatus), nullable=False,
                               default=FlagStatus.pending, index=True)
    instructor_note   = Column(Text, nullable=True)

    flagged_at        = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at       = Column(DateTime(timezone=True), nullable=True)
    last_run_id       = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id"),
                               nullable=True)

    assignment        = relationship("Assignment")
    submission_a      = relationship("Submission", foreign_keys=[submission_a_id],
                                     back_populates="pairs_as_a")
    submission_b      = relationship("Submission", foreign_keys=[submission_b_id],
                                     back_populates="pairs_as_b")
    last_run          = relationship("PipelineRun", foreign_keys=[last_run_id])


# ── PipelineRun ───────────────────────────────────────────────

class PipelineRun(Base):
    """
    Audit row for every analysis run.
    Triggered by instructor via API or by a scheduled job.
    """
    __tablename__ = "pipeline_runs"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id     = Column(UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    triggered_by      = Column(String(64), nullable=False,
                               comment="'instructor', 'scheduler', 'webhook'")
    heuristics_used   = Column(JSON, nullable=False, default=list,
                               comment="List of heuristic names run")
    threshold         = Column(Float, nullable=False, default=0.45,
                               comment="Composite score threshold used for flagging")
    submissions_count = Column(Integer, nullable=False, default=0)
    pairs_evaluated   = Column(Integer, nullable=False, default=0)
    pairs_flagged     = Column(Integer, nullable=False, default=0)
    started_at        = Column(DateTime(timezone=True), server_default=func.now())
    finished_at       = Column(DateTime(timezone=True), nullable=True)
    error             = Column(Text, nullable=True)

    assignment        = relationship("Assignment",    back_populates="pipeline_runs")
    heuristic_scores  = relationship("HeuristicScore", back_populates="run",
                                     cascade="all, delete-orphan")
