import duckdb
import os
import json
from core.logger import logger
from models.config_models import SiteSelector
from sqlalchemy.orm import Session

class DuckDBManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DuckDBManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self.db_path = os.path.join(os.getcwd(), "data", "selectors.duckdb")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = duckdb.connect(self.db_path)
        self._create_schema()
        logger.info(f"DuckDB initialized at {self.db_path}")

    def _create_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS site_selectors (
                id INTEGER PRIMARY KEY,
                ats_platform_id INTEGER,
                job_site_id INTEGER,
                config_json JSON,
                updated_at TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS submitted_jobs (
                job_id VARCHAR PRIMARY KEY,
                job_title VARCHAR,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        logger.info("DuckDB schema verified.")

    def sync_from_mysql(self, mysql_session: Session):
        """Fetches all selectors from MySQL and upserts them into DuckDB."""
        logger.info("Syncing selectors from MySQL to DuckDB...")
        selectors = mysql_session.query(SiteSelector).all()
        
        for s in selectors:
            # Flatten/serialize JSON for DuckDB
            config_str = json.dumps(s.config_json)
            updated_at_str = s.updated_at.isoformat() if s.updated_at else None
            
            self.conn.execute("""
                INSERT OR REPLACE INTO site_selectors (id, ats_platform_id, job_site_id, config_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (s.id, s.ats_platform_id, s.job_site_id, config_str, updated_at_str))
            
        logger.info(f"Synced {len(selectors)} selectors into DuckDB.")

    def get_selectors(self, job_site_id=None, ats_platform_id=None):
        """Fetches merged selectors for a site/platform."""
        query = "SELECT config_json FROM site_selectors WHERE "
        params = []
        
        conditions = []
        if job_site_id:
            conditions.append("job_site_id = ?")
            params.append(job_site_id)
        if ats_platform_id:
            conditions.append("ats_platform_id = ?")
            params.append(ats_platform_id)
            
        if not conditions:
            return {}
            
        query += " OR ".join(conditions)
        
        rows = self.conn.execute(query, params).fetchall()
        
        merged_selectors = {}
        for (cfg_json,) in rows:
            if isinstance(cfg_json, str):
                merged_selectors.update(json.loads(cfg_json))
            else:
                merged_selectors.update(cfg_json) # DuckDB might return dict/json object
                
        return merged_selectors

db_duckdb = DuckDBManager()
