# Plagiarism Signal Panel: Data Architecture & Pipelining

## 1. Architectural Overview
This branch contains the core backend architecture, data models, and pipeline routing logic for the Plagiarism Signal Panel. 

The primary objective of this data layer is to ingest raw code submissions from a Learning Management System (LMS), strictly enforce assignment-level isolation boundaries, and seamlessly route this data to the heuristic calculation engine. Finally, it persists the calculated risk scores and advanced explainability metrics into a highly structured relational database for frontend consumption.

## 2. Technology Stack & Rationale
To ensure native integration with the structural analysis algorithms (which utilize Python's `ast` module and Zhang-Shasha tree-edit distance), the backend ecosystem is unified under **Python 3.11+**.

* **Database Core:** **PostgreSQL**. Chosen over NoSQL alternatives for its superior indexing capabilities, robust JSON field support (critical for dynamic heuristic scoring), and high-performance analytical queries.
* **API Framework:** **FastAPI**. Used to serve highly efficient REST APIs with automatic Swagger documentation.
* **Data Validation:** **Pydantic**. Enforces strict request/response schemas at the entry gates so malformed data never reaches the database.
* **Database ORM & Migrations:** **SQLAlchemy** is used for object-relational mapping, and **Alembic** handles database migrations and version tracking.

---

## 3. Database Schemas (PostgreSQL)
The database is strictly normalized into six core tables to securely manage the data lifecycle without cross-contamination.

1. **`assignments`**: The highest-level logical boundary. Submissions are always compared *within* the same assignment; cross-assignment comparison is strictly prevented at the database level.
2. **`submissions`**: The primary ingestion layer. This stores the raw code, anonymized student IDs, and a normalized token sequence (cached during ingestion to prevent redundant re-tokenization during heuristic runs).
3. **`heuristic_scores`**: An append-only log storing the granular mathematical results from individual pipeline runs (e.g., text overlap percentage, structural match percentage).
4. **`timing_signals`**: Captures submission timestamps to detect localized submission clusters (e.g., catching identical files submitted within minutes of each other).
5. **`flagged_pairs`**: The aggregated output table. This row is generated or updated after every pipeline run. It stores the final composite risk score, risk thresholds (High/Medium/Low), and the **Explainability breakdown** required by the frontend dashboard.
6. **`pipeline_runs`**: An audit trail table that records every analysis run, logging when it was triggered, the specific heuristics used, and the total pairs evaluated.

---

## 4. Pipeline Execution Flow
The pipelining logic acts as the orchestration layer, dictating how data moves securely from ingestion to visualization in four distinct phases:

1. **Ingestion & Request Validation:** Raw code packages arrive via the API. Pydantic schemas immediately validate the payloads (ensuring no missing Student IDs or empty files).
2. **Assignment Isolation:** The routing logic dynamically filters the submissions, organizing them into isolated assignment buckets to guarantee the scope boundary constraint.
3. **Heuristic Engine Handoff:** The organized, clean data is passed directly to the Python-based comparison engine for tokenization, Abstract Syntax Tree (AST) generation, and algorithmic evaluation.
4. **Relational Aggregation:** Once the engine returns the individual scores and timing signals, the data pipeline calculates the final composite risk score and securely commits the payload to the `flagged_pairs` PostgreSQL table.

---

## 5. API Contracts (REST Endpoints)
The system exposes four critical endpoints to connect the LMS, the internal engine, and the React frontend.

* **`POST /submissions`**
  * **Role:** Primary ingestion gateway.
  * **Action:** Accepts payload from the LMS, validates using Pydantic, and stores the raw code in the `submissions` table.
* **`POST /flagged-pairs`**
  * **Role:** Internal processing bridge.
  * **Action:** Allows the Python heuristic engine to write its final calculation results and specific explainability text directly into the database.
* **`GET /flagged-pairs`**
  * **Role:** Dashboard compilation.
  * **Action:** Fetches the aggregated high-risk pairs and serves them to the React frontend to render risk distributions and heatmaps.
* **`GET /flagged-pairs/{id}`**
  * **Role:** Deep-dive Explainability.
  * **Action:** When an instructor selects a specific flagged pair on the UI, this endpoint fetches detailed metadata (e.g., *91% Token Overlap, 88% Structure Match, Submitted 4 Minutes Apart*) to clearly justify the system's flag.

---

## 6. Local Setup & Migration Commands
*(For development and testing only)*

To initialize the database schema and track changes, we utilize Alembic. Run the following commands in your terminal to synchronize the PostgreSQL tables:

```bash
# Generate the initial migration script based on models.py
alembic revision --autogenerate -m "initial"

# Apply the migration to build the PostgreSQL tables
alembic upgrade head
