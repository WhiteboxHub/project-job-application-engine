# Infosys Automation Standalone

This is a standalone repository for automated job applications for Infosys. It has been decoupled from the main job engine for independent use.

## Project Structure
- `infosys_app.py`: The main entry point to run the automation.
- `infosys_strategy.py`: Contains the core logic for finding and applying to jobs.
- `core/`: Browser management, safe actions, and logging.
- `config/`: Configuration and environment settings.
- `data/`: Database connection helpers.
- `models/`: Database schema definitions.

## Setup Instructions

1.  **Environment**: 
    Create a `.env` file in the root directory and populate it with your credentials (copied from the main project).
    ```bash
    DB_HOST=...
    DB_USER=...
    DB_PASSWORD=...
    DB_NAME=...
    RESUME_PATH=...
    # Infosys specific settings
    INFY_SUBMIT=false
    INFY_PAUSE_BEFORE_SUBMIT=true
    ```

2.  **Dependencies**:
    Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run**:
    Execute the standalone automation script:
    ```bash
    python3 infosys_app.py
    ```

## Notes
- By default, `INFY_SUBMIT` is set to `false` for a dry run. Set to `true` to actually submit applications.
- Ensure your Chrome version is compatible with `undetected-chromedriver`.
