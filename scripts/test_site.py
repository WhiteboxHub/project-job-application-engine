"""
Per-Site Test Runner
Tests a single job site in isolation (dry-run by default)

Usage:
    python scripts/test_site.py --site lancesoft      # Test LanceSoft  (dry)
    python scripts/test_site.py --site infosys        # Test Infosys     (dry)
    python scripts/test_site.py --site wipro          # Test Wipro       (dry)
    python scripts/test_site.py --site kforce         # Test KForce      (dry)
    python scripts/test_site.py --site lancesoft --live  # LIVE run (will submit!)
"""
import sys
import os
import json
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_connection import db
from engine.runner import EngineRunner
from core.logger import logger

SITE_MAP = {
    'lancesoft': 'LanceSoft',
    'infosys':   'Infosys',
    'wipro':     'Wipro',
    'kforce':    'KForce',
    'insight':   'Insight Global',  # kept for reference
}

def get_first_candidate(session):
    """Get first active flagged candidate"""
    result = session.execute("""
        SELECT cm.id as cm_id, cm.candidate_id, cm.run_parameters,
               c.full_name, c.email
        FROM candidate_marketing cm
        JOIN candidate c ON cm.candidate_id = c.id
        WHERE cm.marketing_flag = 1
          AND cm.is_processed = 0
          AND cm.status = 'active'
        LIMIT 1
    """)
    return result.fetchone()

def get_site(session, company_name):
    """Get site + platform info"""
    result = session.execute("""
        SELECT s.id, s.company_name, s.domain, s.search_url_template,
               p.id as platform_id, p.name as platform_name,
               p.class_handler, p.automation_level
        FROM job_sites s
        JOIN ats_platforms p ON s.ats_platform_id = p.id
        WHERE s.company_name = ? AND s.is_active = 1
    """, (company_name,))
    return result.fetchone()

def main():
    parser = argparse.ArgumentParser(description="Test a single job site")
    parser.add_argument('--site', required=True,
                        choices=['lancesoft', 'infosys', 'wipro', 'kforce', 'insight'],
                        help='Which site to test')
    parser.add_argument('--live', action='store_true',
                        help='Run LIVE (actually submits). Default is dry-run.')
    args = parser.parse_args()

    dry_run = not args.live
    company_name = SITE_MAP[args.site]

    logger.info("=" * 70)
    logger.info(f"SITE TEST: {company_name}")
    logger.info(f"   Mode: {'LIVE - WILL SUBMIT!' if args.live else 'DRY RUN (safe)'}")
    logger.info("=" * 70)

    session = db.get_session()

    # Get candidate
    candidate = get_first_candidate(session)
    if not candidate:
        logger.error("X No active flagged candidate found in DB.")
        logger.error("   Make sure candidate_marketing has a row with:")
        logger.error("   marketing_flag=1, is_processed=0, status='active'")
        return

    # Handle DuckDB row access (tuple/nametuple check)
    # DuckDB's fetchone() usually returns a tuple if using native connection
    # Let's check if we can access by name. Raw duckdb conn usually doesn't, 
    # but the way EngineRunner is called might need specific indexing if it's a tuple.
    
    # If it's a tuple, map it
    if isinstance(candidate, (tuple, list)):
        # result order: cm.id, cm.candidate_id, cm.run_parameters, c.full_name, c.email
        cm_id, candidate_id, run_parameters, full_name, email = candidate
    else:
        cm_id = candidate.cm_id
        candidate_id = candidate.candidate_id
        run_parameters = candidate.run_parameters
        full_name = candidate.full_name
        email = candidate.email

    logger.info(f"OK Using candidate: {full_name} ({email})")

    # Get site
    site = get_site(session, company_name)
    if not site:
        logger.error(f"X Site '{company_name}' not found in job_sites table or is inactive.")
        return

    if isinstance(site, (tuple, list)):
        # result order: id, company_name, domain, search_url_template, platform_id, platform_name, class_handler, automation_level
        s_id, s_name, s_domain, s_template, p_id, p_name, p_handler, p_auto = site
    else:
        s_id = site.id
        s_name = site.company_name
        p_handler = site.class_handler

    logger.info(f"OK Site found: {s_name} | handler: {p_handler}")

    # Parse run_parameters
    try:
        candidate_data = json.loads(candidate.run_parameters) if candidate.run_parameters else {}
    except Exception:
        candidate_data = {}

    # Build candidate_info dict matching what scheduler_worker passes to EngineRunner
    if isinstance(candidate, (tuple, list)):
        candidate_info = {
            'cm_id':          candidate[0],
            'candidate_id':   candidate[1],
            'run_parameters': candidate[2],
            'full_name':      candidate[3],
            'email':          candidate[4],
            'site_id':        site[0],
            'company_name':   site[1],
            'domain':         site[2],
            'search_url_template': site[3],
            'platform_id':    site[4],
            'platform_name':  site[5],
            'class_handler':  site[6],
            'automation_level': site[7],
        }
    else:
        candidate_info = {
            'cm_id':          candidate.cm_id,
            'candidate_id':   candidate.candidate_id,
            'run_parameters': candidate.run_parameters,
            'full_name':      candidate.full_name,
            'email':          candidate.email,
            'site_id':        site.id,
            'company_name':   site.company_name,
            'domain':         site.domain,
            'search_url_template': site.search_url_template,
            'platform_id':    site.platform_id,
            'platform_name':  site.platform_name,
            'class_handler':  site.class_handler,
            'automation_level': site.automation_level,
        }

    # Set dry_run mode via settings
    from config.settings import settings
    settings.DRY_RUN = dry_run

    try:
        runner = EngineRunner()
        runner.run(site_filter=company_name) # EngineeringRunner likely picks up candidate data from elsewhere or needs to be passed correctly
        logger.info("=" * 70)
        logger.info(f"OK TEST COMPLETE for {company_name}")
        logger.info("=" * 70)
    except Exception as e:
        logger.error(f"X Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == '__main__':
    main()
