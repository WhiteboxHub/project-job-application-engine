# Enterprise Job Application Engine (E-JAE)

![Production Ready](https://img.shields.io/badge/Status-Production--Ready-blue.svg)
![Supported Sites](https://img.shields.io/badge/Sites-KForce%20%7C%20Capgemini%20%7C%20InsightGlobal%20%7C%20LanceSoft%20%7C%20Wipro-green.svg)
![Lines of Code](https://img.shields.io/badge/Lines-800+-brightgreen.svg)
![Python](https://img.shields.io/badge/Python-3.9+-yellow.svg)
![Database](https://img.shields.io/badge/Database-DuckDB-orange.svg)
![Browser](https://img.shields.io/badge/Browser-Undetected--Chrome-red.svg)

## 🏗️ 1. Executive Summary

The **Enterprise Job Application Engine (E-JAE)** is a specialized, production-grade automation framework designed to orchestrate the discovery and application lifecycle across multiple enterprise job portals. It leverages advanced browser automation, human-behavior simulation, and a localized DuckDB backend to provide a unified interface for disparate Applicant Tracking Systems (ATS).

### Supported Platforms:
1.  **KForce**: A stealthy "Guest Apply" flow that bypasses standard bot detection.
2.  **Capgemini**: Authenticated automation for **SAP SuccessFactors**, managing multi-step form filling.
3.  **Insight Global**: Optimized strategy for the Insight Global careers portal.
4.  **LanceSoft**: High-throughput automation for the **JobDiva** platform with advanced pagination.
5.  **Wipro**: Custom strategy for the Wipro talent portal.

This engine is engineered for **stealth**, **reliability**, and **maintainability**, strictly adhering to a **Strictly Database-Driven Architecture**.

---

## 🚀 2. Quick Start Guide

### 2.1 Environmental Prerequisites
- **Operating System**: macOS, Linux, or Windows.
- **Python Runtime**: Version 3.10 or higher.
- **Web Browser**: Latest stable version of Google Chrome.

### 2.2 Installation Steps
```bash
# Step 1: Clone the repository
git clone <repo-url>
cd project-job-application-engine

# Step 2: Initialize a clean virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Step 3: Install all production dependencies
pip install -r requirements.txt
```

### 2.3 Configuration Workflow

1.  **Phase A: Secrets (`.env`)**
    Copy `.env.example` to `.env` and fill in your credentials.
    
2.  **Phase B: Personal Data (`data/guest_form_data.json`)**
    Update your name, email, phone, and resume path.
    
3.  **Phase C: Automation Logic (DuckDB)**
    Run the initializer to seed the database:
    ```bash
    python scripts/init_db.py
    ```

---

## 🎮 3. Usage & Execution

Execute the engine using the unified entry point:

```bash
# Run for a specific site (Dry Run)
python scripts/main.py --site KForce --dry-run
python scripts/main.py --site LanceSoft --dry-run

# Run all active sites
python scripts/main.py
```

### Check Database Status
```bash
python scripts/check_db.py
```

---

## 🏗️ 4. Architecture

### Core Components
- **Engine Layer**: `runner.py` coordinates the workflow, `factory.py` loads strategies, and `guards.py` enforces safety.
- **Strategy Pattern**: Abstract base class (`base.py`) allows easy extension for new sites.
- **Database Layer**: **DuckDB** provides rapid local state storage and history.
- **Browser Automation**: `browser.py` manages an undetected Chrome instance with `human_behavior.py` simulating natural interactions.

---

## 🛡️ 5. Safety Features

1.  **Application Limits**: Configurable max applications per run (`MAX_APPLICATIONS_PER_RUN`).
2.  **Cooldown Period**: Randomized pauses between actions and a fixed wait between applications.
3.  **Dry-Run Mode**: Test the automation safely—it fills forms but stops before final submission.
4.  **Duplicate Detection**: Checks the database before applying to skip previously applied roles.
5.  **reCAPTCHA Handling**: Integrated 120-second manual solve window with automatic countdown.

---

## 🗄️ 6. Database Queries

### View All Discovered Jobs
```bash
python scripts/query_db.py "SELECT job_title, job_url, status FROM job_listings"
```

### View Application History
```bash
python scripts/query_db.py "SELECT job_title, status, applied_at FROM applications ORDER BY applied_at DESC"
```

---

## 📜 7. Maintenance & Troubleshooting
- **Singleton Lock**: If the browser crashes, delete `./chrome_profile/SingletonLock`.
- **Database Reset**: Use `scripts/reset_listings.py` to clear application history.
- **Logs**: Detailed information is available in `engine.log`.
