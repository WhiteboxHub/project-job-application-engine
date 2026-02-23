# 🤖 Job Application Engine

A database-driven job application automation engine built on the **Strategy Pattern**. Supports multi-site automation with job deduplication, audit logging, and Windows Task Scheduler integration.

---

## 🏗️ Architecture

```
scripts/main.py                  ← Manual / single-site entry point
scripts/scheduler_worker.py      ← Scheduled / multi-site entry point

engine/runner.py                 ← Orchestrates browser + strategy per site
engine/factory.py                ← Dynamically loads strategy by class path
engine/guards.py                 ← Enforces application limits

strategies/custom/
  ├── wipro.py                   ← Wipro automation (guest mode)
  ├── infosys.py                 ← Infosys BKS portal
  ├── lancesoft.py               ← LanceSoft / JobDiva
  ├── kforce.py                  ← KForce (guest application)
  └── capgemini.py               ← Capgemini / SAP SuccessFactors

core/
  ├── browser.py                 ← undetected-chromedriver lifecycle
  ├── human_behavior.py          ← Randomised human-like interactions
  ├── safe_actions.py            ← Resilient click / fill helpers
  ├── candidate_loader.py        ← Merges parsed_resume.json + guest_form_data.json
  └── captcha_handler.py         ← reCAPTCHA detection & manual solve prompt

data/
  ├── db_connection.py           ← DuckDB singleton connection
  ├── db_duckdb.py               ← Schema creation & helper queries
  ├── guest_form_data.json       ← Candidate profile & search config
  └── job_engine.duckdb          ← SQLite-style local database file
```

---

## 🗄️ Database (DuckDB)

All configuration and tracking lives in a single file: `data/job_engine.duckdb`

### Configuration tables
| Table | Purpose |
|---|---|
| `ats_platforms` | Automation class path + level per platform |
| `job_sites` | Domain, search URL, application caps |
| `site_selectors` | JSON-encoded CSS selectors (listing & application) |

### Tracking tables
| Table | Purpose |
|---|---|
| `applied_jobs` | Deduplication — prevents re-applying to the same job |
| `scheduler_runs` | Audit log for every automated run |

---

## 🌐 Supported Sites

| # | Site | Automation Level | Status | Notes |
|---|---|---|---|---|
| 1 | **Wipro** | Manual | `is_active=true` | Guest mode, no login |
| 2 | **Infosys** | Manual | `is_active=true` | BKS portal |
| 3 | **LanceSoft** | Full | `is_active=true` | Fully scheduled |
| 4 | **KForce** | Manual | `is_active=false` | Run via `--site` |
| 5 | **Capgemini** | Manual | `is_active=false` | Requires credentials |
| 6 | **Insight Global** | Manual | `is_active=false` | Run via `--site` |

> **`is_active=false`** sites are skipped by the scheduler but can always be run on demand with `--site`.

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment
Copy `.env.example` → `.env` and fill in:
```env
DUCKDB_PATH=data/job_engine.duckdb
RESUME_FILE_PATH=resume/candidate_resume.pdf
HEADLESS=False
KEEP_BROWSER_OPEN=False

# Required for Capgemini only
CAPGEMINI_EMAIL=your@email.com
CAPGEMINI_PASSWORD=yourpassword
```

### 3. Configure candidate profile
Edit `data/guest_form_data.json` — this is the single source of truth for all form-filling:
```jsonc
{
  "applicant": { "first_name": "...", "last_name": "...", "email": "...", ... },
  "search": { "keyword": "AI Engineer", "location": "United States" }
}
```

### 4. Initialise database
```bash
python scripts/init_db.py
```

### 5. Run a site
```bash
python scripts/main.py --site "Infosys"
python scripts/main.py --site "Wipro"
python scripts/main.py --site "LanceSoft"
python scripts/main.py --site "KForce"
python scripts/main.py --site "Capgemini"   # needs .env credentials
```

---

## ⚙️ Windows Task Scheduler (Automated Daily Runs)

The `run_scheduler.bat` script is designed to be triggered daily by Task Scheduler.

```
run_scheduler.bat
  └── starts scheduler_worker.py
        └── runs all is_active=true sites in sequence
              └── logs results to scheduler_runs table
```

**Setup:**
1. Open **Task Scheduler** → *Create Task*
2. **General** tab → ✅ "Run with highest privileges"
3. **Triggers** → Daily at your preferred time
4. **Actions** → Start `run_scheduler.bat` (set "Start in" to project root)
5. **Conditions** → Uncheck "Start only if on AC power"

---

## 🔧 Utility Scripts

| Script | Purpose |
|---|---|
| `scripts/init_db.py` | Create tables + seed all site configs |
| `scripts/seed_kforce_capgemini.py` | Seed KForce & Capgemini selectors |
| `scripts/seed_wipro_selectors.py` | Seed Wipro selectors |
| `scripts/check_db.py` | Print DB summary (tables, row counts, sites) |
| `scripts/check_active_sites.py` | List active sites and their configs |
| `scripts/check_selectors.py` | Show all loaded selectors per site |
| `scripts/query_db.py` | Run an arbitrary DuckDB query |
| `scripts/list_sites.py` | Quick site list |
| `scripts/parse_resume.py` | Parse a PDF resume → `parsed_resume.json` |
| `scripts/reset_listings.py` | Clear `applied_jobs` for fresh testing |
| `scripts/verify_readiness.py` | Pre-flight check before a run |
| `scripts/test_site.py` | Test automation for a specific site |
| `scripts/scheduler_worker.py` | Multi-site automation runner |

---

## 📁 Data Files

| File | Purpose |
|---|---|
| `data/guest_form_data.json` | Candidate profile, search config, credentials |
| `data/parsed_resume.json` | Auto-generated by `parse_resume.py` |
| `data/applied_jobs.json` | CSV-based fallback deduplication |
| `resume/candidate_resume.pdf` | Resume file for upload |

---

## 📄 License
MIT License.
