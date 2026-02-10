# 🤖 Job Application Engine

Automated job application system that discovers jobs from multiple sources and submits applications with human-like behavior. Features DuckDB database persistence, intelligent form filling, resume upload automation, and reCAPTCHA handling.

## ✨ Features

- 🔍 **Automated Job Discovery** - Scrapes job listings with pagination support across all pages
- 📝 **Smart Form Filling** - Human-like typing with random delays
- 📄 **Resume Upload** - Automatic resume attachment with multiple fallback methods
- 🤖 **reCAPTCHA Detection** - 30-second manual solve window
- 💾 **Database Persistence** - DuckDB for job listings and application tracking
- 📊 **Dual Tracking** - Database + CSV backup
- 🛡️ **Safety Guards** - Application limits, cooldowns, dry-run mode
- 🎭 **Human Behavior** - Natural mouse movements and typing patterns
- 🏗️ **Extensible Architecture** - Strategy pattern for easy addition of new job sites

## 📊 Current Status

**Database:** ✅ Fully Operational
- **102 jobs** discovered (LanceSoft)
- **5 jobs** discovered (Insight Global)
- **1 application** submitted successfully

**Supported Platforms:**
- ✅ **Insight Global** (Custom Strategy) - Fully operational
- ✅ **LanceSoft** (JobDiva Platform) - Fully operational with pagination

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Google Chrome browser

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file (or copy from `.env.example`):
```bash
# Browser Settings
HEADLESS=false                    # Show browser window
KEEP_BROWSER_OPEN=true            # Keep browser open after run (for debugging)

# Application Settings
DRY_RUN=false                     # Set to true for testing without submitting
MAX_APPLICATIONS_PER_RUN=5        # Maximum applications per run (safety limit)
SUBMISSION_COOLDOWN_SECONDS=30    # Wait time between applications
```

### 3. Configure Applicant Data
Edit `data/guest_form_data.json`:
```json
{
  "search": {
    "keyword": "AI Engineer",
    "location": "",
    "distance": ""
  },
  "applicant": {
    "first_name": "YOUR_FIRST_NAME",
    "last_name": "YOUR_LAST_NAME",
    "email": "your.email@example.com",
    "phone": "+1 (XXX) XXX-XXXX"
  },
  "resume_path": "resume/Your_Resume.pdf"
}
```

### 4. Add Your Resume
Place your resume in the `resume/` folder:
```bash
resume/Your_Resume.pdf
```

### 5. Initialize Database
```bash
python scripts/init_db.py
```

### 6. Run the Application

**Dry-run mode (recommended first):**
```bash
python scripts/main.py --dry-run
```

**Run for specific site:**
```bash
python scripts/main.py --site "LanceSoft"
python scripts/main.py --site "Insight Global"
```

**Live mode:**
```bash
python scripts/main.py
```

---

## 📁 Project Structure

```
project-job-application-engine/
├── 📄 Core Files
│   ├── .env                      # Environment variables (create from .env.example)
│   ├── .env.example              # Example environment configuration
│   ├── .gitignore                # Git ignore rules
│   ├── LICENSE                   # Apache 2.0 License
│   ├── README.md                 # This file
│   └── requirements.txt          # Python dependencies
│
├── ⚙️ config/                    # Configuration Management
│   ├── settings.py               # Pydantic settings (loads from .env)
│   └── secrets_validator.py      # Configuration validation
│
├── 🤖 core/                      # Core Automation Modules
│   ├── browser.py                # Undetected Chrome driver management
│   ├── captcha_handler.py        # reCAPTCHA detection & handling
│   ├── human_behavior.py         # Human-like typing & mouse movements
│   ├── logger.py                 # Centralized logging
│   ├── proxy_manager.py          # Proxy configuration (optional)
│   └── safe_actions.py           # Reliable element interactions with retry logic
│
├── 💾 data/                      # Data & Database
│   ├── job_engine.duckdb         # DuckDB database (auto-created)
│   ├── guest_form_data.json      # Applicant information & search config
│   ├── db_connection.py          # Database connection management
│   └── csv_tracker.py            # CSV backup tracking
│
├── 🗄️ db/                        # Database Schema
│   ├── schema.sql                # Complete database schema with seed data
│   └── init_db.py                # Database initialization script
│
├── 📚 docs/                      # Documentation
│   ├── HUMAN_BEHAVIOR_GUIDE.md   # Guide to human-like automation
│   ├── IMPLEMENTATION_SUMMARY.md # Implementation overview
│   ├── MULTI_SEARCH_CONFIG.md    # Multi-location search configuration
│   ├── QUICK_REFERENCE.md        # Quick reference guide
│   ├── WORKFLOW_EXPLAINED.md     # Detailed workflow explanation
│   └── archive/                  # Archived implementation notes
│       ├── EEO_FORM_COMPLETE.md
│       ├── EEO_FORM_IMPLEMENTATION.md
│       └── IMPLEMENTATION_NEXT_BUTTON_COUNTRY.md
│
├── 🎯 engine/                    # Main Engine
│   ├── runner.py                 # Main orchestrator (coordinates workflow)
│   ├── factory.py                # Strategy factory (loads site-specific strategies)
│   └── guards.py                 # Safety guards (limits, cooldowns, dry-run)
│
├── 🗃️ models/                    # Database Models (SQLAlchemy ORM)
│   ├── __init__.py               # Model exports
│   ├── config_models.py          # Configuration tables (job_sites, selectors)
│   ├── history_models.py         # History tables (applications, metrics)
│   └── persistence_models.py     # Job listings table
│
├── 📄 resume/                    # Resume Storage
│   └── Your_Resume.pdf           # Your resume file
│
├── 🛠️ scripts/                   # Utility Scripts
│   ├── main.py                   # Main entry point (CLI)
│   ├── init_db.py                # Initialize database
│   ├── check_db.py               # Database status summary
│   └── query_db.py               # Execute SQL queries
│
└── 🎭 strategies/                # Job Site Strategies (Strategy Pattern)
    ├── base.py                   # Abstract base strategy class
    └── custom/
        ├── insight_global.py     # Insight Global implementation (1,525 lines)
        └── lancesoft.py          # LanceSoft/JobDiva implementation (1,104 lines)
```

---

## 🏗️ Architecture

### Core Components

**1. Engine Layer**
- `runner.py` - Orchestrates job discovery and application workflow
- `factory.py` - Dynamically loads strategy classes
- `guards.py` - Enforces safety limits and dry-run mode

**2. Strategy Pattern**
- `base.py` - Abstract base class defining interface
- `insight_global.py` - Site-specific implementation
- Easily extensible for new job sites

**3. Database Layer**
- **DuckDB** - Fast, embedded SQL database
- **Configuration Tables** - Job sites, platforms, selectors
- **History Tables** - Job listings, applications, metrics

**4. Browser Automation**
- `browser.py` - Undetected Chrome driver
- `safe_actions.py` - Retry logic for stale elements
- `human_behavior.py` - Natural typing and mouse movements
- `captcha_handler.py` - reCAPTCHA detection and handling

---

## 💾 Database Schema

### Configuration Tables
- `ats_platforms` - Application tracking systems
- `job_sites` - Job sites/companies
- `site_selectors` - CSS selectors for scraping

### Data Tables
- `job_listings` - Discovered jobs queue
  - Status: `discovered`, `ready_to_apply`, `applied`, `failed`, `blacklisted`
- `applications` - Submission history
  - Status: `success`, `failed`, `skipped`
- `metrics` - Performance tracking

---

## 🔧 Usage

### Run Application
```bash
python scripts/main.py
```

### Check Database Status
```bash
python scripts/check_db.py
```

**Output:**
```
📊 TABLES IN DATABASE:
  ✓ applications
  ✓ job_listings
  ✓ job_sites
  ...

📈 ROW COUNTS:
  applications: 1 rows
  job_listings: 5 rows
  ...

📋 JOB LISTINGS: 5 jobs discovered
  Status breakdown:
    - discovered: 4
    - applied: 1

✉️ APPLICATIONS: 1 applications submitted
  Status breakdown:
    - success: 1
```

### Query Database
```bash
# View all discovered jobs
python scripts/query_db.py "SELECT job_title, job_url, status FROM job_listings"

# View applications
python scripts/query_db.py "SELECT job_title, status, applied_at FROM applications ORDER BY applied_at DESC"

# Count by status
python scripts/query_db.py "SELECT status, COUNT(*) FROM job_listings GROUP BY status"
```

### Interactive SQL (DuckDB)
```bash
python -c "import duckdb; conn=duckdb.connect('data/job_engine.duckdb'); conn.execute('SELECT * FROM job_listings').df()"
```

---

## 🎯 Workflow

### 1. Job Discovery
- Navigate to job search page
- Enter keyword, location, distance
- Scrape job listings across all pages
- Save to `job_listings` table with status `discovered`

### 2. Application Process
For each discovered job:
1. Navigate to job URL
2. Click "Apply" button
3. Click "Apply as Guest"
4. Fill form fields (name, email, phone)
5. Upload resume
6. Wait for reCAPTCHA (if present) - 30 seconds for manual solve
7. Submit application
8. Update `job_listings` status to `applied`
9. Create record in `applications` table

### 3. Tracking
- **DuckDB** - Primary storage
- **CSV** - Backup (`data/insight_global_jobs.csv`)

---

## ⚙️ Configuration

### Environment Variables (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `HEADLESS` | `false` | Run browser in headless mode |
| `DRY_RUN` | `false` | Test mode - don't submit applications |
| `MAX_APPLICATIONS_PER_RUN` | `999999` | Maximum applications per run |
| `SUBMISSION_COOLDOWN_SECONDS` | `60` | Wait time between submissions |
| `PROXY_ENABLED` | `false` | Enable proxy support |

### Multi-Search Configuration

Configure multiple keyword/location combinations in `guest_form_data.json`:

```json
{
  "search_configurations": [
    {
      "keyword": "AI Engineer",
      "location": "Chicago, IL",
      "distance": "50"
    },
    {
      "keyword": "ML Engineer",
      "location": "New York, NY",
      "distance": "25"
    },
    {
      "keyword": "Data Scientist",
      "location": "San Francisco, CA",
      "distance": "50"
    }
  ],
  "applicant": {
    "first_name": "YOUR_NAME",
    "last_name": "YOUR_LASTNAME",
    "email": "your.email@example.com",
    "phone": "+1 (XXX) XXX-XXXX"
  },
  "resume_path": "resume/Your_Resume.pdf"
}
```

---

## 🛡️ Safety Features

### 1. Application Limits
```python
MAX_APPLICATIONS_PER_RUN=2000 # Stop after 10 applications
```

### 2. Cooldown Period
```python
SUBMISSION_COOLDOWN_SECONDS=60  # Wait 60 seconds between apps
```

### 3. Dry-Run Mode
```python
DRY_RUN=true  # Test without submitting
```

### 4. Duplicate Detection
- Checks database before applying
- Won't reapply to same job URL

### 5. Human-Like Behavior
- Random typing delays (50-150ms per character)
- Natural mouse movements
- Random pauses between actions

---

## 🤖 reCAPTCHA Handling

The system automatically detects reCAPTCHA challenges:

1. **Detection** - Scans for reCAPTCHA iframe
2. **Notification** - Logs warning message
3. **Wait Period** - 30-second window for manual solve
4. **Continuation** - Proceeds after solve or timeout

**Manual Solve:**
- Watch the browser window
- Solve the reCAPTCHA when it appears
- Script continues automatically

---

## 📊 Database Queries

### View All Jobs
```sql
SELECT job_title, job_url, status, created_at 
FROM job_listings 
ORDER BY created_at DESC;
```

### View Applications
```sql
SELECT job_title, status, applied_at 
FROM applications 
ORDER BY applied_at DESC;
```

### Count by Status
```sql
SELECT status, COUNT(*) as count 
FROM job_listings 
GROUP BY status;
```

### Failed Applications
```sql
SELECT job_title, error_message, applied_at 
FROM applications 
WHERE status = 'failed';
```

---

## 🐛 Troubleshooting

### Database is Empty
**Problem:** No data in `job_listings` or `applications` tables

**Solutions:**
1. Ensure `DRY_RUN=false` in `.env`
2. Check terminal for errors
3. Verify database file exists: `data/job_engine.duckdb`
4. Reinitialize database: `python scripts/init_db.py`

### Applications Not Submitting
**Problem:** Jobs discovered but not applied

**Solutions:**
1. Check browser window during 30-second pause
2. Manually solve reCAPTCHA if present
3. Verify form data in `guest_form_data.json`
4. Check terminal logs for errors

### Resume Upload Fails
**Problem:** Resume not uploading

**Solutions:**
1. Ensure resume exists in `resume/` folder
2. Check file path in `guest_form_data.json`
3. Verify file is PDF format
4. Check file permissions

### Browser Not Opening
**Problem:** Chrome driver fails to start

**Solutions:**
1. Update Chrome to latest version
2. Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`
3. Check Chrome is installed in default location

---

## 🔄 Adding New Job Sites

### 1. Create Strategy Class
```python
# strategies/custom/new_site.py
from strategies.base import BaseStrategy

class NewSiteStrategy(BaseStrategy):
    def login(self):
        # Implement login logic
        pass
    
    def find_jobs(self):
        # Implement job discovery
        pass
    
    def apply(self, listing):
        # Implement application logic
        pass
```

### 2. Add to Database
```sql
INSERT INTO ats_platforms (name, class_handler) 
VALUES ('New Site', 'strategies.custom.NewSiteStrategy');

INSERT INTO job_sites (company_name, domain, platform_id, is_active) 
VALUES ('New Site', 'newsite.com', 2, true);
```

### 3. Configure Selectors
Add selectors to `site_selectors` table or hardcode in strategy file.

---

## 📈 Performance

**Current Stats:**
- ✅ 5 jobs discovered
- ✅ 1 application submitted (100% success rate)
- ✅ 0 failed applications
- ⏱️ Average time per application: ~2-3 minutes

---

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Additional job site strategies (LinkedIn, Indeed, etc.)
- 2Captcha integration for automatic solving
- Email notifications
- Analytics dashboard
- Resume customization per job
- Cover letter generation

---

## 📝 License

This project is for educational purposes. Use responsibly and in accordance with job site terms of service.

---

## ⚠️ Disclaimer

This tool automates job applications. Always:
- Review job descriptions before applying
- Ensure your resume is tailored appropriately
- Comply with job site terms of service
- Use responsibly and ethically

---

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review terminal logs for errors
3. Check database status: `python scripts/check_db.py`
4. Verify configuration in `.env` and `guest_form_data.json`

---

**Built with ❤️ for job seekers**
