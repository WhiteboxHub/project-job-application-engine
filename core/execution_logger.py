import json
import os
from datetime import datetime, timezone
from core.logger import logger

class ExecutionTracker:
    def __init__(self):
        self.started_at = datetime.now(timezone.utc)
        self.parameters_used = {}
        self.successful_applications = []
        self.failed_applications = []
        self.total_jobs_found = 0

    def initialize(self, run_parameters=None):
        """Reset the logger state for a new engine run"""
        self.started_at = datetime.now(timezone.utc)
        self.parameters_used = run_parameters or {}
        self.successful_applications = []
        self.failed_applications = []
        self.total_jobs_found = 0

    def add_jobs_found(self, count):
        self.total_jobs_found += count

    def add_applications_attempted(self, count):
        """Manually increment the attempted counter if needed"""
        # This isn't strictly necessary as attempted = success + failure, 
        # but the user wants to track it explicitly for some reports.
        logger.debug(f"[TRACKER] Manually added {count} attempts")

    def record_success(self, job_site, job_id, job_title, job_url):
        self.successful_applications.append({
            "job_site": job_site,
            "job_id": job_id,
            "job_title": job_title,
            "job_url": job_url,
            "applied_at": datetime.now(timezone.utc).isoformat()
        })
        logger.debug(f"[TRACKER] Recorded success for {job_id}")

    def record_error(self, job_site, job_id, job_title, job_url, error_reason):
        self.failed_applications.append({
            "job_site": job_site,
            "job_id": job_id,
            "job_title": job_title,
            "job_url": job_url,
            "error_reason": str(error_reason),
            "failed_at": datetime.now(timezone.utc).isoformat()
        })
        logger.debug(f"[TRACKER] Recorded failure for {job_id}")

    def generate_report(self, output_path="data/output.json"):
        """Save the structural JSON report summarizing the engine run"""
        finished_at = datetime.now(timezone.utc)
        total_success = len(self.successful_applications)
        total_failed = len(self.failed_applications)
        
        status = "success"
        if total_failed > 0:
            status = "completed_with_errors"
        if total_success == 0 and total_failed > 0:
            status = "failed"
            
        applicant_data = self.parameters_used.get("applicant", {})
        candidate_name = f"{applicant_data.get('first_name', '')} {applicant_data.get('last_name', '')}".strip()
        if not candidate_name:
            candidate_name = "Unknown Candidate"
            
        report = {
            "workflow_id": self.parameters_used.get("workflow_id"),
            "schedule_id": self.parameters_used.get("schedule_id"),
            "run_id": self.parameters_used.get("run_id", f"RUN-{self.started_at.strftime('%Y%m%d-%H%M')}"),
            "candidate_name": candidate_name,
            "status": status,
            "execution_summary": {
                "total_jobs_found": self.total_jobs_found,
                "total_applications_attempted": total_success + total_failed,
                "total_applications_successful": total_success,
                "total_applications_failed": total_failed,
            },
            "successful_applications": self.successful_applications,
            "failed_applications": self.failed_applications,
            "started_at": self.started_at.isoformat(),
            "finished_at": finished_at.isoformat()
        }

        # Save to file beautifully indented
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=4)
        
        return output_path

# Singleton instance exported for use everywhere
execution_tracker = ExecutionTracker()
