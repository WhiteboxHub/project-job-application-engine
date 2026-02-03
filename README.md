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

### Data Layer (`data/`)
-   **CSV Storage**: Uses CSV files for tracking application history and job discovery. Each site has its own CSV file (e.g., `insight_global_jobs.csv`) that tracks job status, attempts, and timestamps.

### Strategies (`strategies/`)
-   **Base Strategy**: Abstract Base Class defining the interface (`login`, `find_jobs`, `apply`).
-   **Custom Strategies**: Implementations for specific sites (e.g., `strategies.custom.insight_global.InsightGlobalStrategy`).

---

## 🚀 Installation & Setup

### Prerequisites
-   Python 3.10+
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
-   `CHROME_USER_DATA_DIR`: Path to your Chrome profile (optional).
-   `RESUME_FILE_PATH`: Path to your resume file for upload (optional).

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
-   **CSV Tracking**: Job discovery and application status tracked in CSV files for easy monitoring.
-   **Human-Like Behavior**: 
    -   Random delays between form fields (1-2 seconds)
    -   Natural typing speed (50-150ms per character)
    -   Smooth scrolling to elements
    -   Mouse movements before clicks
-   **Smart CAPTCHA Handling**:
    -   Automatic CAPTCHA click attempts
    -   30-second manual solve window (configurable)
    -   Optional 2Captcha API integration
    -   Multiple detection strategies

See [`docs/HUMAN_BEHAVIOR_GUIDE.md`](docs/HUMAN_BEHAVIOR_GUIDE.md) for detailed usage.

