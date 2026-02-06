# Job Application Engine

A robust, automated job application engine designed to discover and apply to jobs across various ATS platforms using `undetected-chromedriver`.

## 🏗 Architecture

The project follows a modular, layered architecture designed for stability and extensibility.

### Core Architecture (`core/`)
-   **Browser Management**: Uses `undetected-chromedriver` to bypass bot detection. Includes a **Profile Mutex** (`browser.py`) to prevent profile corruption by ensuring only one instance runs at a time.
-   **Safe Actions** (`safe_actions.py`): A wrapper around Selenium interactions that handles:
    -   `StaleElementReferenceException` retries.
    -   Human-like delays and micro-movements.
    -   Validation of element existence.
-   **Proxy Manager** (`proxy_manager.py`): Supports rotating residential proxies.

### Engine Layer (`engine/`)
-   **Factory Pattern** (`factory.py`): Dynamically loads strategy classes based on the `class_handler` string stored in the `ats_platforms` database table.
-   **Orchestraion** (`runner.py`): Manages the high-level loop: Discovery -> Validation -> Application.
-   **Safety Guards** (`guards.py`): Enforces limits like `MAX_APPLICATIONS_PER_RUN` and handles `DRY_RUN` logic.

### Data Layer (`data/`, `models/`)
-   **Configuration DB (MySQL)**: Stores `JobSite`, `AtsPlatform`, and `SiteSelector` configurations. Allows changing selectors without deploying code.
-   **Persistence DB (DuckDB)**: Local file-based database for tracking application history (`applications` table) and execution metrics (`metrics` table).

### Strategies (`strategies/`)
-   **Base Strategy**: Abstract Base Class defining the interface (`login`, `find_jobs`, `apply`).
-   **Custom Strategies**: Implementations for specific sites (e.g., `strategies.custom.infosys.InfosysStrategy`).

---

## 🚀 Installation & Setup

### Prerequisites
-   Python 3.10+
-   MySQL / MariaDB Server
-   Google Chrome

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy the example environment file:
```bash
cp .env.example .env
```
Edit `.env` with your credentials:
-   `DB_PASSWORD`: Your MySQL root password.
-   `CHROME_USER_DATA_DIR`: Path to your Chrome profile (optional).

### 3. Initialize Databases
Run the migration script to create tables in MySQL and DuckDB:
```bash
python3 scripts/init_db.py
```

---

## 💻 Usage

### CLI Commands
The main entry point is `scripts/main.py`.

**Run Normal Execution:**
```bash
python3 scripts/main.py
```

**Dry Run Mode** (Navigates and fills forms but DOES NOT click submit):
```bash
python3 scripts/main.py --dry-run
```

**Headless Mode** (Run in background):
```bash
python3 scripts/main.py --headless
```

### Configuration
Adjust run parameters in `.env`:
```ini
MAX_APPLICATIONS_PER_RUN=10
SUBMISSION_COOLDOWN_SECONDS=30
```

---

## 🛡 Features
-   **Anti-Detection**: Uses `undetected-chromedriver` v2.
-   **Profile Locking**: Prevents concurrent access to the Chrome profile.
-   **Retry Framework**: Automatically retries clicks/typing on transient errors.
-   **Database Driven**: Selectors and strategies are configured in SQL, allowing dynamic updates.
