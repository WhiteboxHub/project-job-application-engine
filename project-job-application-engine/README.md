# 🤖 Wellfound Job Discovery Engine

A high-performance, stealth-enabled automation tool designed for discovering AI/ML job opportunities on **Wellfound**.

---

## 🛠️ Setup Guide

### 1. Install Dependencies
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
Create a `.env` file:
```env
DUCKDB_PATH=data/job_engine.duckdb
HEADLESS=False
WELLFOUND_MAX_PAGES=3
```

---

## 🚀 Usage Guide

This project follows a structured **Strategy Pattern**. All site-specific logic and selectors are decentralized into strategies and the database.

### Step 1: Initialize Database
Always run this first to set up the tracking tables and load Wellfound selectors into the database.
```bash
python scripts/init_db.py
```

### Step 2: Start discovery
Run the main engine to begin the discovery process:
```bash
python scripts/main.py
```
> [!NOTE]
> Select **Option 1** to start the Wellfound discovery engine. The engine will use the selectors stored in DuckDB and follow the `WellfoundStrategy` logic.

---

## 📁 Project Architecture

- **`strategies/custom/wellfound.py`**: Contains the core logic for navigating Wellfound and bypassing bot detection.
- **`engine/`**: The orchestration layer. `EngineRunner` fetches selectors from DuckDB and executes the strategy.
- **`scripts/seed_wellfound_selectors.py`**: Dedicated script for loading Wellfound-specific CSS selectors into the database.
- **`data/`**: Stores your tracking database (`job_engine.duckdb`) and logs.
- **`scripts/`**: Entry points for the application.

---

## 🧠 Features

- **🎯 Strategy Pattern**: Cleanly separated logic for easy maintainability.
- **💾 Database-Driven**: Selectors are stored in DuckDB, allowing for updates without changing the code.
- **🛡️ Anti-Bot Stealth**: Human-like movements and scrolling to bypass advanced detection.
- **🔍 Automated Deduplication**: Automatically tracks and filters already discovered jobs.
