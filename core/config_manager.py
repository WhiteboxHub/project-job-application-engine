
"""
Configuration Manager for Database-Driven Configuration

This module provides centralized access to all database-driven configuration:
- Selectors (CSS/XPath)
- Field keywords (for smart fill)
- Field values (EEO, preferences)
- Section keywords (for section detection)
- Search filters (job search criteria)
"""

from sqlalchemy import or_
from core.logger import logger
from models.config_models import SiteSelector
# Missing models in current database schema
# from models.config_models import (
#     FieldKeyword,
#     FieldValue,
#     SectionKeyword,
#     SearchFilter,
#     UrlConfig
# )


class ConfigManager:
    """
    Centralized configuration manager for database-driven config
    
    Provides methods to retrieve selectors, keywords, values, and filters
    from the database with caching and fallback support.
    """
    
    def __init__(self, db_session, job_site_id):
        """
        Initialize ConfigManager
        
        Args:
            db_session: SQLAlchemy database session
            job_site_id: ID of the job site
        """
        self.db = db_session
        self.job_site_id = job_site_id
        self._cache = {}
    
    # ========================================================================
    # SELECTORS
    # ========================================================================
    
    def get_selectors(self, selector_key):
        """
        Get selector values for a given key
        
        Args:
            selector_key: Key identifying the selector (e.g., 'apply_button')
            
        Returns:
            list: List of selector strings
        """
        cache_key = f"selector_{selector_key}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            # Robust check for SQLAlchemy vs Raw DuckDB
            use_sqlalchemy = hasattr(self.db, 'query') and 'sqlalchemy' in str(type(self.db)).lower()
            
            if use_sqlalchemy:
                # SQLAlchemy
                selectors = self.db.query(SiteSelector).filter(
                    SiteSelector.job_site_id == self.job_site_id
                ).all()
                config_jsons = [s.config_json for s in selectors]
            else:
                # Raw DuckDB
                import json
                rows = self.db.execute(
                    "SELECT config_json FROM site_selectors WHERE job_site_id = ?",
                    [self.job_site_id]
                ).fetchall()
                config_jsons = []
                for (cj,) in rows:
                    if isinstance(cj, str):
                        config_jsons.append(json.loads(cj))
                    else:
                        config_jsons.append(cj)
            
            result = []
            for config in config_jsons:
                if config and isinstance(config, dict):
                    if selector_key in config:
                        val = config[selector_key]
                        if isinstance(val, list):
                            result.extend(val)
                        elif isinstance(val, str):
                            result.append(val)
            
            # Remove duplicates while preserving order
            final_result = list(dict.fromkeys(result))
            
            self._cache[cache_key] = final_result
            
            if final_result:
                logger.debug(f"ConfigManager: Loaded {len(final_result)} selectors for '{selector_key}'")
            return final_result
        except Exception as e:
            logger.error(f"ConfigManager: Error loading selectors for '{selector_key}': {e}")
            return []

    def get_field_keywords(self, field_name):
        """Get keywords for a specific field name from config_json"""
        cache_key = f"keywords_{field_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            use_sqlalchemy = hasattr(self.db, 'query') and 'sqlalchemy' in str(type(self.db)).lower()
            
            if use_sqlalchemy:
                # SQLAlchemy
                selectors = self.db.query(SiteSelector).filter(
                    SiteSelector.job_site_id == self.job_site_id
                ).all()
                config_jsons = [s.config_json for s in selectors]
            else:
                # Raw DuckDB
                import json
                rows = self.db.execute(
                    "SELECT config_json FROM site_selectors WHERE job_site_id = ?",
                    [self.job_site_id]
                ).fetchall()
                config_jsons = []
                for (cj,) in rows:
                    if isinstance(cj, str):
                        config_jsons.append(json.loads(cj))
                    else:
                        config_jsons.append(cj)
            
            for config in config_jsons:
                if config and isinstance(config, dict):
                    if "field_keywords" in config:
                        kws = config["field_keywords"].get(field_name)
                        if kws:
                            result = kws if isinstance(kws, list) else [kws]
                            self._cache[cache_key] = result
                            return result
            
            return []
        except Exception as e:
            logger.error(f"ConfigManager: Error loading field keywords for '{field_name}': {e}")
            return []

    # ========================================================================
    # FIELD VALUES (Disabled - Missing Model)
    # ========================================================================
    
    def get_field_value(self, field_name, context=None):
        """Get field value from config_json as fallback"""
        try:
            use_sqlalchemy = hasattr(self.db, 'query') and 'sqlalchemy' in str(type(self.db)).lower()
            
            if use_sqlalchemy:
                selectors = self.db.query(SiteSelector).filter(
                    SiteSelector.job_site_id == self.job_site_id
                ).all()
                config_jsons = [s.config_json for s in selectors]
            else:
                import json
                rows = self.db.execute(
                    "SELECT config_json FROM site_selectors WHERE job_site_id = ?",
                    [self.job_site_id]
                ).fetchall()
                config_jsons = []
                for (cj,) in rows:
                    if isinstance(cj, str): config_jsons.append(json.loads(cj))
                    else: config_jsons.append(cj)
            
            for config in config_jsons:
                if config and isinstance(config, dict):
                    if "field_values" in config:
                        val = config["field_values"].get(field_name)
                        if val: return val
            return None
        except Exception:
            return None
    
    def get_all_field_values(self, context=None):
        return {}
    
    # ========================================================================
    # SECTION KEYWORDS
    # ========================================================================
    
    def get_section_keywords(self, section_name):
        """Get keywords identifying a section from config_json"""
        return self.get_field_keywords(section_name) # Keywords are keywords
    
    # ========================================================================
    # SEARCH FILTERS
    # ========================================================================
    
    def get_search_filters(self, filter_type):
        """Get search filters (target_keyword, blocked_keyword, etc) from config_json"""
        return self.get_selectors(filter_type)
    
    # ========================================================================
    # URL CONFIGURATION
    # ========================================================================
    
    def get_url(self, url_key, **kwargs):
        """Get URL templates from config_json"""
        try:
            use_sqlalchemy = hasattr(self.db, 'query') and 'sqlalchemy' in str(type(self.db)).lower()
            
            if use_sqlalchemy:
                selectors = self.db.query(SiteSelector).filter(
                    SiteSelector.job_site_id == self.job_site_id
                ).all()
                config_jsons = [s.config_json for s in selectors]
            else:
                import json
                rows = self.db.execute(
                    "SELECT config_json FROM site_selectors WHERE job_site_id = ?",
                    [self.job_site_id]
                ).fetchall()
                config_jsons = []
                for (cj,) in rows:
                    if isinstance(cj, str): config_jsons.append(json.loads(cj))
                    else: config_jsons.append(cj)
            
            for config in config_jsons:
                if config and isinstance(config, dict):
                    if "urls" in config:
                        url = config["urls"].get(url_key)
                        if url: return url
            return None
        except Exception:
            return None
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def clear_cache(self):
        """Clear the configuration cache"""
        self._cache = {}
        logger.info("ConfigManager: Cache cleared")
    
    def reload(self):
        """Reload all configuration from database"""
        self.clear_cache()
        logger.info("ConfigManager: Configuration reloaded")
