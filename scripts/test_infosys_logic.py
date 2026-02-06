
import sys
import os
from unittest.mock import MagicMock

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.custom.infosys import InfosysStrategy
from config.settings import settings

def test_infosys_strategy_logic():
    print("Testing Infosys Strategy logic with mocked driver...")
    
    # Mock driver
    mock_driver = MagicMock()
    mock_driver.page_source = "<html><body>Infosys Careers</body></html>"
    mock_driver.current_url = "https://digitalcareers.infosys.com/"
    
    # Mock job site
    class MockJobSite:
        def __init__(self):
            self.name = "Infosys"
            self.base_url = "https://digitalcareers.infosys.com"
            self.search_url_template = "https://digitalcareers.infosys.com/search?keyword={keyword}"
            self.keyword = "AI Engineer"
            self.location = "USA"
            
    # Mock selectors
    selectors = {
        "search": {
            "keyword": "AI Engineer",
            "job_links": [["css selector", "a.job-link"]]
        }
    }
    
    try:
        strategy = InfosysStrategy(mock_driver, MockJobSite(), selectors)
        print("Strategy initialized successfully.")
        
        # Test helper methods
        is_target = strategy._is_target_job("AI Engineer")
        print(f"Target job check (AI Engineer): {is_target}")
        
        ats = strategy._detect_infosys_ats()
        print(f"ATS detection: {ats}")
        
        # Test basic flow (should mostly run and call mock methods)
        strategy.login()
        print("Login logic executed.")
        
        print("Logic test passed successfully!")
    except Exception as e:
        print(f"Logic test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_infosys_strategy_logic()
