# 🤖 Job Application Engine

A database-driven, multi-site job application automation engine built on the **Strategy Pattern**. Each job board has its own self-contained strategy module. Configuration, deduplication, and execution metadata live in the **MotherDuck Cloud** (or local DuckDB), while the candidate data and scheduling are directly orchestrated by the central **wbl-backend API**.

---

## 🏗️ Architecture & Data Flow

The engine operates on a seamless, zero-touch dynamic pipeline:

1. **Trigger Phase:** The engine (`scripts/main.py`) hits the backend API (`/api/weekly-workflow/trigger-run`) to check for pending automated workflows scheduled for the current time.
2. **Data Injection:** The backend constructs the candidate's profile, including keywords, experience, and the resume link, and returns it as a JSON payload (`run_parameters`).
3. **Resume Download:** The `resume_downloader` parses the `resume_url` (Google Drive) and securely downloads the PDF into `resume/downloads/`. 
4. **Execution:** The completely assembled payload is injected into memory, meaning the engine **NO LONGER** relies on local configuration files like `guest_form_data.json`.
5. **Sequential Application:** The engine automatically queries the database for all active platforms mapped for full automation and executes them sequentially using the injected candidate data.

---

## ☁️ Database Configuration

The system uses a **Local DuckDB database** (`data/job_engine.duckdb`) to track application states locally.

### Control Tables
| Table | Purpose |
|---|---|
| `ats_platforms` | Platform class handler (`strategies.custom.mysite`) and `automation_level` ('full', 'semi', etc.). |
| `job_sites` | Target portal details (e.g., LanceSoft, Experis) and the boolean `is_active` flag. |
| `site_selectors` | HTML/CSS selectors per website injected at runtime to resist UI changes. |

> **IMPORTANT:** When `main.py` is run without site parameters, it will automatically query the database and execute ALL sites where `is_active = true` AND `automation_level = 'full'`.

---

## 🚀 Quick Start Guide

### 1. Install Dependencies

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)

Copy `.env.example` to `.env` and fill in your details:

```env
# Database
DUCKDB_PATH=data/job_engine.duckdb

# Backend Integration
BACKEND_URL=https://api.whitebox-learning.com/api
TRIGGER_ENDPOINT=/weekly-workflow/trigger-run
INTERNAL_SECRET_KEY=your_secure_auth_key


# Execution Specs
HEADLESS=False
KEEP_BROWSER_OPEN=False
DOWNLOADED_RESUME_DIR=resume/downloads/
```

### 3. Initialize the Database

*Note: You only need to run this if you are ADDING a new company to the database or doing a local test! Otherwise, the data is already in MotherDuck.*
```bash
python scripts/init_db.py
```

### 4. Running the Engine

**Run dynamically (via Backend API):**
```bash
# Fetches data from the backend API, downloads the resume, and runs ALL active sites sequentially
python scripts/main.py
```

**Testing a specific site:**
```bash
python scripts/main.py --site "Experis"
```

---

## ⏰ Windows Task Scheduler Deployment

The engine is built to be deployed via **Windows Task Scheduler** for daily or weekly background operation.

1. Configure a `Daily` trigger in Windows Task Scheduler.
2. Set the Action to run a batch script (`run_engine.bat`) that activates the `venv` and calls `python scripts/main.py`.
3. **How it syncs:** Every day, the script will ping the backend. If it's time to run a job (e.g., exactly one week since the last run), the backend will provide the payload and automatically update its `last_run` and `next_run` timestamps.
4. If it is *not* time to run yet, the backend returns an empty response, and the script silently shuts down.

---

## 🧠 Adding a New Company Strategy

Because different ATS platforms operate differently, we use the Strategy Pattern.

1. **Create Class:** Create a new file `strategies/custom/new_company.py` that inherits from `BaseStrategy`.
2. **Implement Logic:** Implement `login()`, `find_jobs()`, and `apply()`.
3. **Access Internal Data:** Use `self.candidate_data` generated during initialization to fill out forms dynamically.
4. **Register Entrypoint:** Add your class to `strategies/custom/__init__.py`.
5. **Add to Database:** Insert the company mapping into `ats_platforms` and `job_sites` via `scripts/init_db.py`. Ensure `is_active=True` and `automation_level='full'` to put it in the active automated pipeline!
