# 🤖 Job Application Engine

A database-driven, multi-site job application automation engine built on the **Strategy Pattern**. Each job board has its own self-contained strategy module. Configuration, deduplication, and audit logging all live in the **MotherDuck Cloud** (or local DuckDB).

---

## ☁️ Database (MotherDuck Cloud / Local DuckDB)

The project supports both local DuckDB and MotherDuck (Cloud) for team collaboration.
When using MotherDuck, the entire team safely shares the same database securely in the cloud. We use this to instantly sync new ATS platform settings, job sites, and CSS selectors with everyone on the team!

### Configuration tables

| Table | Purpose |
|---|---|
| `ats_platforms` | ATS platform name, automation class path, automation level |
| `job_sites` | Company name, domain, search URL, daily application cap |
| `site_selectors` | Per-site CSS selectors stored as JSON (listing + application) |

### Tracking tables (Memory)

| Table | Purpose |
|---|---|
| `applied_jobs` | Deduplication — prevents anyone on the team from re-applying to the same job |
| `scheduler_runs` | Audit log for every automated run (timestamp, counts, errors) |

---

## 🌐 Supported Sites

| # | Site | Automation Level | Status | Notes |
|---|---|---|---|---|
| 1 | **Wipro** | Semi-auto | Active | Guest mode; SAP UI5 JS extraction |
| 2 | **Infosys** | Full-auto | Active | BKS portal; full form fill + upload |
| 3 | **LanceSoft** | Full-auto | Active | JobDiva portal; scheduled daily |
| 4 | **Insight Global**| Semi-auto | Paused | Run on-demand with `--site` |
| 5 | **KForce** | Semi-auto | Paused | Guest application flow |
| 6 | **Capgemini** | Semi-auto | Paused | Requires login credentials |
| 7 | **Hiring Cafe** | Semi-auto | Paused | Aggregator portal |

---

## 🚀 Quick Start Guide for Developers

### 1. Install dependencies

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment (`.env`)

Copy `.env.example` to `.env` and fill in your details:

```env
# Sync to the cloud with MotherDuck (Required for team sync)
DUCKDB_PATH=md:job_engine
MOTHERDUCK_TOKEN=your_token_here

RESUME_FILE_PATH=resume/candidate_resume.pdf
HEADLESS=False
KEEP_BROWSER_OPEN=False
```

### 3. Configure Candidate Data

Edit `data/guest_form_data.json` — this is the single source of truth for the person you are actually applying for! Fill in their address, experience, and keywords here.

### 4. Parse your resume

```bash
python scripts/parse_resume.py
```
This reads your PDF and creates a structured payload for the forms.

### 5. Initialise the database

```bash
python scripts/init_db.py
```
*Note: If you are connecting to MotherDuck cloud, you only need to run this if you are ADDING a new company to the database! Otherwise, your data is already synced!*

### 6. Run a site!

```bash
# Run one active site
python scripts/main.py --site "Wipro"

# Or let the scheduler run all active sites sequentially!
python scripts/scheduler_worker.py
```

---

## 🧠 How the Strategy Pattern Works

Because everyone adds new companies differently, we use a Strategy Pattern. 
When the engine runs a site, here is what happens:

1. `runner.py` asks the database what Python class handles the chosen company (e.g. `strategies.custom.WiproStrategy`).
2. `factory.py` dynamically loads that Python file and hands it the browser.
3. The strategy uses `.find_jobs()` to gather the job listings on the page.
4. `runner.py` checks the MotherDuck brain to remove jobs we already applied for.
5. `runner.py` feeds the clean jobs back into the strategy's `.apply()` method.
6. Successful applications are saved in MotherDuck so the whole team knows it's done.

### How to Add a New Site to the Engine:

1. Create a new file like `strategies/custom/mysite.py`. You must extend `BaseStrategy`!
2. Write the logic for `login()`, `find_jobs()`, and `apply()`.
3. Open `strategies/custom/__init__.py` and add your class to the `__all__` list!
4. Open `scripts/init_db.py` and write the SQL to INSERT your new company into the database.
5. Run `python scripts/init_db.py` to push your SQL changes and CSS selectors to the MotherDuck Cloud.
6. Push your branch to GitHub. The whole team now has your strategy!
