# 🤖 Job Application Engine

An automated job application system that applies to jobs on behalf of candidates using Selenium-based browser automation. Supports multiple job portals with a database-driven configuration system.

---

## ✨ Features

- **Multi-site automation** — Infosys, LanceSoft, Insight Global
- **Scheduler-driven** — runs daily via Windows Task Scheduler or cron
- **Database-driven config** — selectors, keywords, and URLs stored in MySQL
- **Candidate management** — per-candidate `marketing_flag` ON/OFF switch
- **Resume parsing** — auto-extracts skills and keywords from PDF resumes
- **Application tracking** — logs every run to MySQL `automation_logs` table
- **Dry-run mode** — test the full flow without submitting any applications
- **Human behavior simulation** — randomized delays, mouse movements, typing speed

---

## 🏗️ Architecture

```
project-job-application-engine/
├── config/              # App settings (settings.py)
├── core/                # Browser, logger, human behavior, captcha handler
├── data/                # Runtime tracking (csv_tracker.py, db_connection.py)
├── db/                  # SQL schema and migrations
├── docs/                # Developer documentation
├── engine/              # Runner, factory, application guards
├── logs/automation/     # Per-run log files (gitignored)
├── models/              # SQLAlchemy models
├── resume/              # Candidate resume files (gitignored)
├── scripts/             # Operational scripts (scheduler, migrations, utilities)
└── strategies/
    ├── base.py          # Abstract base strategy
    └── custom/
        ├── infosys.py       # Infosys Digital Careers automation
        ├── lancesoft.py     # LanceSoft JobDiva portal automation
        └── insight_global.py # Insight Global automation
```

---

## ⚙️ Setup

### 1. Prerequisites

- Python 3.10+
- MySQL 8.0+
- Google Chrome + ChromeDriver (matching version)
- `pdfplumber` (for resume parsing)

### 2. Clone & Install

```bash
git clone https://github.com/your-username/project-job-application-engine.git
cd project-job-application-engine

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=new_db
```

### 4. Initialize Database

```bash
python scripts/init_db.py
python scripts/run_migration.py
```

### 5. Add a Candidate

Insert a row into `candidate_marketing` with `marketing_flag = 1`, `status = 'active'`, and a **DIRECT PDF LINK** for `resume_url`, then populate `run_parameters`:

```bash
python scripts/populate_run_parameters.py
```

---

## 🚀 Running

### Test Specific Site (Recommended)

```bash
python scripts/test_site.py --site infosys
python scripts/test_site.py --site lancesoft
python scripts/test_site.py --site insight
```

### Live Run (Submits Applications)

```bash
python scripts/test_site.py --site lancesoft --live
```

### Full Scheduler Run

```bash
python scripts/scheduler_worker.py
```

### Dry Run (Full Scheduler)

```bash
python scripts/scheduler_worker.py --dry-run
```

---

## 🗄️ Database Schema

| Table | Purpose |
|---|---|
| `ats_platforms` | Platform registry (Infosys, LanceSoft, etc.) with `automation_level` |
| `job_sites` | Site config — URL templates, strategy class path |
| `site_selectors` | CSS/XPath selectors per site |
| `candidate_marketing` | Candidates + `marketing_flag`, `run_parameters`, `is_processed` |
| `automation_logs` | Per-run results and error logs |
| `job_listings` | Discovered jobs |

### `run_parameters` JSON structure

```json
{
  "search": {
    "keywords": ["AI Engineer", "Machine Learning"],
    "location": "USA",
    "distance": "50"
  },
  "applicant": {
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane@example.com",
    "phone": "555-1234"
  }
}
```

---

## 🔄 Automation Levels

| Level | Behavior |
|---|---|
| `fully` | Picked up automatically by the scheduler |
| `semi` | Requires manual trigger |
| `manual` | Not automated |

---

## 📋 Key Scripts

| Script | Purpose |
|---|---|
| `test_site.py` | **Primary Test Tool** — run individual site tests |
| `scheduler_worker.py` | **Main Scheduler** — runs all active candidates |
| `populate_run_parameters.py` | Populate `run_parameters` from resume URL + DB |
| `reset_processed_flag.py` | Reset `is_processed = 0` to re-enable candidates |
| `parse_resume.py` | Parse a PDF resume to JSON (utility) |
| `run_migration.py` | Apply DB migrations |
| `init_db.py` | Initialize the database schema |

---

## 🔒 Security Notes

- **Never commit `.env`** — it contains database credentials
- **Never commit `resume/`** — contains personal candidate data
- Both are gitignored by default

---

## 📅 Scheduling (Windows)

Use Windows Task Scheduler to run daily:

```
Program: C:\path\to\venv\Scripts\python.exe
Arguments: C:\path\to\scripts\scheduler_worker.py
Trigger: Daily at 9:00 AM
```

See `docs/WORKFLOW_EXPLAINED.md` for a full walkthrough.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
