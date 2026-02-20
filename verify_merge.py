import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from engine.factory import strategy_factory
    from models.config_models import JobSite
except ImportError as e:
    print(f"Critical Import Error: {e}")
    sys.exit(1)

def mock_driver():
    class Mock:
        def __init__(self):
            self.page_source = ""
            self.current_url = ""
    return Mock()

def test_load():
    print("Testing Strategy Loading...")
    
    strategies = [
        ("strategies.custom.InsightGlobalStrategy", "Insight Global"),
        ("strategies.custom.LanceSoftStrategy", "LanceSoft"),
        ("strategies.custom.kforce.KForceStrategy", "KForce"),
        ("strategies.custom.capgemini.CapgeminiStrategy", "Capgemini")
    ]
    
    failures = 0
    
    for class_path, name in strategies:
        try:
            print(f"Loading {name} ({class_path})...")
            # Mock objects
            driver = mock_driver()
            site = JobSite(id=1, search_url_template="http://test")
            selectors = {'listing': {}, 'application': {}}
            
            # Try to instantiate
            strategy = strategy_factory.get_strategy(class_path, driver, site, selectors)
            print(f"✅ Successfully loaded {name}")
        except Exception as e:
            print(f"❌ Failed to load {name}: {e}")
            import traceback
            traceback.print_exc()
            failures += 1

    if failures == 0:
        print("\nAll strategies loaded successfully!")
    else:
        print(f"\n{failures} strategies failed to load.")
        sys.exit(1)

if __name__ == "__main__":
    test_load()
