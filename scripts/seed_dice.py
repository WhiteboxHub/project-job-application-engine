
import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_connection import db
from models.config_models import JobSite, SiteSelector, AtsPlatform
from core.logger import logger

def seed_dice():
    """Seed the database with Dice.com configuration"""
    session = db.get_session()
    try:
        logger.info("Seeding Dice.com data...")
        
        # 1. Add ATS Platform
        dice_platform = session.query(AtsPlatform).filter_by(id=5).first()
        if not dice_platform:
            dice_platform = AtsPlatform(
                id=5,
                name='Dice Platform',
                class_handler='strategies.custom.dice.DiceStrategy',
                is_headless_required=False
            )
            session.add(dice_platform)
            logger.info("Added Dice Platform")
        
        # 2. Add Job Site
        dice_site = session.query(JobSite).filter_by(id=5).first()
        if not dice_site:
            dice_site = JobSite(
                id=5,
                company_name='Dice',
                domain='dice.com',
                ats_platform_id=5,
                category='Staffing vendor',
                search_url_template='https://www.dice.com/jobs?q={keyword}&l={location}',
                is_active=True,
                max_applications_per_run=10
            )
            session.add(dice_site)
            logger.info("Added Dice Job Site")
            
        # 3. Add Site Selectors
        listing_selector = session.query(SiteSelector).filter_by(id=7).first()
        if not listing_selector:
            listing_config = {
                "container": "dices-search-results-card, .card",
                "fields": {
                    "title": {
                        "selector": "a.card-title-link",
                        "type": "text"
                    },
                    "url": {
                        "selector": "a.card-title-link",
                        "attr": "href"
                    }
                }
            }
            listing_selector = SiteSelector(
                id=7,
                job_site_id=5,
                type='listing',
                config_json=listing_config
            )
            session.add(listing_selector)
            logger.info("Added Dice Listing Selectors")

        session.commit()
        logger.info("Dice.com seeding completed successfully!")
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error seeding Dice.com: {e}")
    finally:
        db.close_session(session)

if __name__ == "__main__":
    seed_dice()
