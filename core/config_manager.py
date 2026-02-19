
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
            # Fetch all SiteSelector records for this site
            selectors = self.db.query(SiteSelector).filter(
                SiteSelector.job_site_id == self.job_site_id
            ).all()
            
            result = []
            for s in selectors:
                if s.config_json and isinstance(s.config_json, dict):
                    if selector_key in s.config_json:
                        val = s.config_json[selector_key]
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
    
    # ========================================================================
    # FIELD KEYWORDS (Disabled - Missing Model)
    # ========================================================================
    
    def get_field_keywords(self, field_name):
        return []

    # ========================================================================
    # FIELD VALUES (Disabled - Missing Model)
    # ========================================================================
    
    def get_field_value(self, field_name, context=None):
        return None
    
    def get_all_field_values(self, context=None):
        return {}
    
    # ========================================================================
    # SECTION KEYWORDS (Disabled - Missing Model)
    # ========================================================================
    
    def get_section_keywords(self, section_name):
        return []
    
    # ========================================================================
    # SEARCH FILTERS (Disabled - Missing Model)
    # ========================================================================
    
    def get_search_filters(self, filter_type):
        return []
    
    # ========================================================================
    # URL CONFIGURATION (Disabled - Missing Model)
    # ========================================================================
    
    def get_url(self, url_key, **kwargs):
        # Fallback to None so strategy uses its own hardcoded URL
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
