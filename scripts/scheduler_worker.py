"""
Scheduler Worker - Main automation orchestration script

This script is designed to be run by Windows Task Scheduler at a specified time.
It queries candidates flagged for automation, loads their parameters from the database,
executes job application strategies, and logs all results.

Usage:
    python scripts/scheduler_worker.py [--dry-run] [--candidate-id ID]
"""
import sys
import os
import json
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from data.db_connection import db
from config.settings import settings
from engine.runner import EngineRunner
from core.logger import logger

class SchedulerWorker:
    """Orchestrates automated job applications for flagged candidates"""
    
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.session = db.get_session()
        self.results = {
            'candidates_processed': 0,
            'total_applications': 0,
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
    def get_flagged_candidates(self, candidate_id=None):
        """
        Query candidates flagged for automation
        
        Returns list of dicts with candidate and site information
        """
        query = """
            SELECT 
                cm.id as cm_id,
                cm.candidate_id,
                cm.run_parameters,
                c.full_name,
                c.email,
                s.id as site_id,
                s.company_name,
                s.domain,
                s.search_url_template,
                p.id as platform_id,
                p.name as platform_name,
                p.class_handler,
                p.automation_level
            FROM candidate_marketing cm
            JOIN candidate c ON cm.candidate_id = c.id
            CROSS JOIN job_sites s
            JOIN ats_platforms p ON s.ats_platform_id = p.id
            WHERE cm.marketing_flag = 1 
              AND cm.is_processed = 0
              AND cm.status = 'active'
              AND s.is_active = 1
              AND p.automation_level = 'fully'
        """
        
        # Optional: filter by specific candidate
        if candidate_id:
            query += f" AND cm.candidate_id = {candidate_id}"
            
        query += " ORDER BY cm.candidate_id, s.id"
        
        result = self.session.execute(text(query))
        rows = result.fetchall()
        
        # Convert to list of dicts
        candidates = []
        for row in rows:
            candidates.append({
                'cm_id': row[0],
                'candidate_id': row[1],
                'run_parameters': json.loads(row[2]) if row[2] else {},
                'full_name': row[3],
                'email': row[4],
                'site_id': row[5],
                'company_name': row[6],
                'domain': row[7],
                'search_url_template': row[8],
                'platform_id': row[9],
                'platform_name': row[10],
                'class_handler': row[11],
                'automation_level': row[12]
            })
        
        return candidates
    
    def run_automation_for_candidate_site(self, candidate_info):
        """
        Execute automation for a specific candidate × site combination
        
        Args:
            candidate_info: Dict with candidate and site details
            
        Returns:
            Dict with execution results
        """
        candidate_id = candidate_info['candidate_id']
        site_name = candidate_info['company_name']
        
        logger.info(f"🎯 Processing: {candidate_info['full_name']} → {site_name}")
        
        try:
            # Create log directory
            log_dir = Path("logs") / "automation" / datetime.now().strftime("%Y-%m-%d")
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Log file path
            timestamp = datetime.now().strftime("%H%M%S")
            log_file = log_dir / f"candidate_{candidate_id}_{site_name}_{timestamp}.log"
            
            # Setup file logging for this run
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            logger.addHandler(file_handler)
            
            # Run the automation using EngineRunner
            runner = EngineRunner()
            
            # Override settings if dry run
            if self.dry_run:
                settings.DRY_RUN = True
                logger.info("🔍 DRY RUN MODE - No applications will be submitted")
            
            # Execute for this specific site with candidate data
            result = runner.run(
                site_filter=site_name,
                candidate_data=candidate_info['run_parameters']
            )
            
            # Remove file handler
            logger.removeHandler(file_handler)
            file_handler.close()
            
            # Log to automation_logs table
            self.log_automation_result(
                candidate_id=candidate_id,
                site_id=candidate_info['site_id'],
                status='success',
                log_file_path=str(log_file),
                applications_count=result.get('applications_submitted', 0) if result else 0
            )
            
            logger.info(f"✅ Completed: {candidate_info['full_name']} → {site_name}")
            
            return {
                'status': 'success',
                'applications': result.get('applications_submitted', 0) if result else 0,
                'log_file': str(log_file)
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing {candidate_info['full_name']} → {site_name}: {e}")
            
            # Log error to automation_logs
            self.log_automation_result(
                candidate_id=candidate_id,
                site_id=candidate_info['site_id'],
                status='failed',
                error_message=str(e),
                log_file_path=str(log_file) if 'log_file' in locals() else None
            )
            
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def log_automation_result(self, candidate_id, site_id, status, log_file_path=None, 
                             error_message=None, applications_count=0):
        """Insert result into automation_logs table"""
        try:
            insert_query = text("""
                INSERT INTO automation_logs 
                (candidate_id, job_site_id, status, log_file_path, error_message, applications_count, timestamp)
                VALUES 
                (:candidate_id, :site_id, :status, :log_file, :error, :count, NOW())
            """)
            
            self.session.execute(insert_query, {
                'candidate_id': candidate_id,
                'site_id': site_id,
                'status': status,
                'log_file': log_file_path,
                'error': error_message,
                'count': applications_count
            })
            self.session.commit()
            
        except Exception as e:
            logger.error(f"Failed to log automation result: {e}")
            self.session.rollback()
    
    def mark_candidate_processed(self, cm_id):
        """Mark candidate_marketing record as processed"""
        try:
            update_query = text("""
                UPDATE candidate_marketing 
                SET is_processed = 1, 
                    last_processed_at = NOW()
                WHERE id = :cm_id
            """)
            
            self.session.execute(update_query, {'cm_id': cm_id})
            self.session.commit()
            logger.info(f"✅ Marked candidate_marketing ID {cm_id} as processed")
            
        except Exception as e:
            logger.error(f"Failed to mark candidate as processed: {e}")
            self.session.rollback()
    
    def run(self, candidate_id=None):
        """
        Main execution method
        
        Args:
            candidate_id: Optional - process only this candidate
        """
        logger.info("=" * 80)
        logger.info("🚀 SCHEDULER WORKER STARTED")
        logger.info("=" * 80)
        logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info("")
        
        try:
            # Get flagged candidates
            candidates = self.get_flagged_candidates(candidate_id)
            
            if not candidates:
                logger.info("ℹ️  No candidates flagged for automation")
                logger.info("   Set marketing_flag = 1 in candidate_marketing table to enable")
                return
            
            logger.info(f"📋 Found {len(candidates)} candidate × site combinations to process")
            logger.info("")
            
            # Group by candidate_id to track which candidates we've processed
            processed_cm_ids = set()
            
            # Process each candidate × site combination
            for idx, candidate_info in enumerate(candidates, 1):
                logger.info(f"[{idx}/{len(candidates)}] Processing...")
                
                # Run automation
                result = self.run_automation_for_candidate_site(candidate_info)
                
                # Track results
                if result['status'] == 'success':
                    self.results['successful'] += 1
                    self.results['total_applications'] += result.get('applications', 0)
                else:
                    self.results['failed'] += 1
                    self.results['errors'].append({
                        'candidate': candidate_info['full_name'],
                        'site': candidate_info['company_name'],
                        'error': result.get('error')
                    })
                
                # Track which candidate_marketing IDs we've processed
                processed_cm_ids.add(candidate_info['cm_id'])
                
                logger.info("")
            
            # Mark all processed candidates
            for cm_id in processed_cm_ids:
                self.mark_candidate_processed(cm_id)
            
            self.results['candidates_processed'] = len(processed_cm_ids)
            
            # Print summary
            self.print_summary()
            
        except Exception as e:
            logger.critical(f"❌ Fatal error in scheduler worker: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        finally:
            self.session.close()
    
    def print_summary(self):
        """Print execution summary"""
        logger.info("=" * 80)
        logger.info("📊 EXECUTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Candidates processed:     {self.results['candidates_processed']}")
        logger.info(f"Total applications:       {self.results['total_applications']}")
        logger.info(f"Successful:               {self.results['successful']}")
        logger.info(f"Failed:                   {self.results['failed']}")
        
        if self.results['errors']:
            logger.info("")
            logger.info("❌ Errors:")
            for error in self.results['errors']:
                logger.info(f"   - {error['candidate']} → {error['site']}: {error['error']}")
        
        logger.info("=" * 80)
        logger.info("✅ SCHEDULER WORKER COMPLETED")
        logger.info("=" * 80)


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scheduler Worker - Automated Job Applications")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Run without submitting applications")
    parser.add_argument("--candidate-id", type=int, 
                       help="Process only this candidate ID")
    
    args = parser.parse_args()
    
    # Create and run worker
    worker = SchedulerWorker(dry_run=args.dry_run)
    worker.run(candidate_id=args.candidate_id)


if __name__ == "__main__":
    main()
