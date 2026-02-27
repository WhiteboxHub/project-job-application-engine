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
from sqlalchemy import text

SITE_MAP = {
    'lancesoft': 'LanceSoft',
    'infosys':   'Infosys',
    'wipro':     'Wipro',
    'kforce':    'KForce',
    'insight':   'Insight Global',  # kept for reference
    'capgemini': 'Capgemini',
}

class DummyCandidate:
    pass

def get_first_candidate(session):
    """Get candidate from guest_form_data.json instead of db"""
    json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "guest_form_data.json")
    with open(json_path, 'r') as f:
        data = json.load(f)

    app = data.get("applicant", {})
    full_name = f"{app.get('first_name', '')} {app.get('last_name', '')}".strip()
    
    cand = DummyCandidate()
    cand.cm_id = 999
    cand.candidate_id = 999
    cand.run_parameters = json.dumps(data)
    cand.full_name = full_name
    cand.email = app.get("email", "")
    return cand

class DummySite:
    pass

def get_site(session, company_name):
    """Get site + platform info"""
    result = session.execute("""
        SELECT s.id, s.company_name, s.domain, s.search_url_template,
               p.id as platform_id, p.name as platform_name,
               p.class_handler, p.automation_level
        FROM job_sites s
        JOIN ats_platforms p ON s.ats_platform_id = p.id
        WHERE s.company_name = ? AND s.is_active = 1
    """, [company_name])
    row = result.fetchone()
    if row:
        s = DummySite()
        s.id = row[0]
        s.company_name = row[1]
        s.domain = row[2]
        s.search_url_template = row[3]
        s.platform_id = row[4]
        s.platform_name = row[5]
        s.class_handler = row[6]
        s.automation_level = row[7]
        return s
    return None

def main():
    parser = argparse.ArgumentParser(description="Test a single job site")
    parser.add_argument('--site', required=True,
                        choices=['lancesoft', 'infosys', 'wipro', 'kforce', 'insight', 'capgemini'],
                        help='Which site to test')
    parser.add_argument('--live', action='store_true',
                        help='Run LIVE (actually submits). Default is dry-run.')
    parser.add_argument('--keywords', type=str,
                        help='Override search keywords (comma-separated)')
    args = parser.parse_args()

    dry_run = not args.live
    company_name = SITE_MAP[args.site]

    logger.info("=" * 70)
    logger.info(f"🧪 SITE TEST: {company_name}")
    logger.info(f"   Mode: {'🔴 LIVE — WILL SUBMIT!' if args.live else '🟡 DRY RUN (safe)'}")
    logger.info("=" * 70)

    session = db.get_session()

    # Get candidate
    candidate = get_first_candidate(session)
    if not candidate:
        logger.error("❌ No active flagged candidate found in DB.")
        logger.error("   Make sure candidate_marketing has a row with:")
        logger.error("   marketing_flag=1, is_processed=0, status='active'")
        return

    logger.info(f"✅ Using candidate: {candidate.full_name} ({candidate.email})")

    # Get site
    site = get_site(session, company_name)
    if not site:
        logger.error(f"❌ Site '{company_name}' not found in job_sites table or is inactive.")
        return

    logger.info(f"✅ Site found: {site.company_name} | handler: {site.class_handler}")

    # Parse run_parameters
    try:
        candidate_data = json.loads(candidate.run_parameters) if candidate.run_parameters else {}
    except Exception:
        candidate_data = {}

    # Build candidate_info dict matching what scheduler_worker passes to EngineRunner
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
    
    if args.keywords:
        logger.info(f"🔑 Overriding keywords with: {args.keywords}")
        # Generic keyword override for strategy search/apply methods
        # Most strategies check config_data['search']['keywords']
        if 'search' not in candidate_data:
            candidate_data['search'] = {}
        candidate_data['search']['keywords'] = [k.strip() for k in args.keywords.split(',')]

    try:
        runner = EngineRunner()
        runner.run(site_filter=company_name, candidate_data=candidate_data)
        logger.info("=" * 70)
        logger.info(f"✅ TEST COMPLETE for {company_name}")
        logger.info("=" * 70)
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == '__main__':
    main()
