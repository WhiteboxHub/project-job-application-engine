import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from engine.runner import EngineRunner
    print("✅ Successfully imported EngineRunner")
    
    runner = EngineRunner()
    print("✅ Successfully initialized EngineRunner instance")
    
except Exception as e:
    print(f"❌ Failed to import or initialize EngineRunner: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
