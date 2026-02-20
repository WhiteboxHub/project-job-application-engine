# 🤖 Job Application Engine

An automated job application system that applies to jobs on behalf of candidates using Selenium-based browser automation. Supports multiple job portals with a database-driven configuration system using DuckDB and MySQL.

---

## ✨ Features

- **Multi-site automation** — Wipro, Hiring Cafe, Infosys, LanceSoft, Insight Global, Kforce, Capgemini
- **Integrated Architecture** — Consolidated multi-site integration branch
- **Database-driven config** — Selectors, keywords, and URLs stored in DuckDB (`data/job_engine.duckdb`)
- **Automated Seeding** — Unified initialization and seeding script for all sites
- **Resume parsing** — Auto-extracts skills and keywords from PDF resumes
- **Application tracking** — Logs applications concurrently in DuckDB and CSV
- **Dry-run mode** — Test discovery and form pre-filling without final submission
- **Human behavior simulation** — Randomized delays, mouse movements, and typing speed

---

## 🏗️ Architecture

```
project-job-application-engine/
├── config/              # App settings (settings.py, hiring_cafe.json)
├── core/                # Browser, logger, human behavior, captcha handler, safe actions
├── data/                # Database and tracking (duckdb, csv_tracker.py, db_connection.py)
├── db/                  # SQL schema and migration definitions
├── engine/              # Main runner, strategy factory, application guards
├── models/              # SQLAlchemy models for DuckDB (config & history)
├── resume/              # Candidate resume files (gitignored)
├── scripts/             # Operational scripts (init, test, scrape, scheduler)
└── strategies/
    ├── base.py          # Abstract base strategy
    └── custom/
        ├── wipro.py          # Wipro Custom Portal (Fully Automated)
        ├── hiring_cafe.py    # Hiring Cafe Job Scraper & ATS Link Extractor
        ├── infosys.py        # Infosys Digital Careers automation
        ├── lancesoft.py      # LanceSoft JobDiva portal automation
        ├── insight_global.py # Insight Global automation
        ├── kforce.py         # Kforce portal automation
        └── capgemini.py      # Capgemini careers automation
```

---

## ⚙️ Setup

### 1. Prerequisites

- Python 3.10+
- Google Chrome + ChromeDriver (auto-managed by browser service)
- `pdfplumber` (for resume parsing)
- `duckdb`, `sqlalchemy`

### 2. Clone & Install

```bash
git clone https://github.com/your-username/project-job-application-engine.git
cd project-job-application-engine

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

### 3. Initialize & Seed Integrated Sites

This unified script sets up the DuckDB schema and seeds configurations for Wipro, Hiring Cafe, and more.

```bash
python scripts/init_and_seed_integrated.py
```

---

## 🚀 Running

### Test Wipro Automation (Dry Run)

```bash
python scripts/test_wipro_dry.py
```

### Scrape Hiring Cafe

```bash
# Standalone scraper (Step 1-3 combined)
python scripts/scrape_hiring_cafe.py --output hiring_cafe_results.json

# Or via the pipeline steps
python scripts/hiring_cafe_step1_extract_urls.py
python scripts/hiring_cafe_step2_extract_ats_urls.py
python scripts/hiring_cafe_step3_combine_by_ats.py
```

### Run General Engine Runner

```bash
python -m scripts.main --site Wipro
```

---

## 🗄️ Database Schema (DuckDB)

| Table | Purpose |
|---|---|
| `ats_platforms` | Platform registry (Wipro Custom, Hiring Cafe Custom, etc.) |
| `job_sites` | Site config — URL templates, strategy class path |
| `site_selectors` | CSS/XPath selectors (stored as JSON) per site |
| `job_listings` | Discovered jobs queue and history |
| `applications` | Application submission history |

---

## 📋 Key Scripts

| Script | Purpose |
|---|---|
| `init_and_seed_integrated.py` | **One-click Setup** — initializes and seeds the entire database |
| `test_wipro_dry.py` | **Wipro Test Tool** — verifies discovery and application flow |
| `scrape_hiring_cafe.py` | **Hiring Cafe All-in-one** — scraps jobs and extracts ATS links |
| `scheduler_worker.py` | **Main Scheduler** — runs all active candidates |
| `run_migration.py` | Apply DB migrations |

---

## 🔒 Security Notes

- **Never commit `.env`** — it contains sensitive credentials
- **Never commit `resume/`** — contains personal candidate data
- **Never commit `*.duckdb`** — database files are gitignored by default

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
