"""
Demo: Human Behavior and CAPTCHA Handler

This script demonstrates how to use the HumanBehavior and CaptchaHandler classes
in your automation scripts.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.common.by import By
from core.human_behavior import HumanBehavior
from core.captcha_handler import CaptchaHandler


def demo_human_behavior():
    """Demonstrate human-like form filling"""
    print("="*60)
    print("DEMO: Human-Like Form Filling")
    print("="*60)
    
    driver = webdriver.Chrome()
    human = HumanBehavior(driver)
    
    try:
        # Navigate to a form page
        driver.get("https://www.example.com")
        
        # Example 1: Random delays
        print("\n1. Random delay (1-3 seconds)...")
        HumanBehavior.random_delay(1, 3)
        print("   ✓ Complete")
        
        # Example 2: Scroll with human-like behavior
        print("\n2. Scrolling page...")
        human.scroll_page(direction='down', amount=500)
        print("   ✓ Complete")
        
        # Example 3: Fill text field with human-like typing
        # Note: This is just an example - replace with actual element
        # element = driver.find_element(By.ID, "email")
        # human.fill_text_field(element, "user@example.com")
        # print("   ✓ Typed with human-like delays")
        
        print("\n✅ Human behavior demo complete!")
        
    finally:
        driver.quit()


def demo_captcha_handler():
    """Demonstrate CAPTCHA handling strategies"""
    print("\n" + "="*60)
    print("DEMO: CAPTCHA Handler")
    print("="*60)
    
    driver = webdriver.Chrome()
    captcha = CaptchaHandler(driver, timeout=30)
    
    try:
        # Navigate to a page with CAPTCHA
        # driver.get("https://www.google.com/recaptcha/api2/demo")
        
        # Strategy 1: Countdown (30 seconds)
        print("\n1. Countdown Strategy (30s wait)")
        print("   - Automatically proceeds after 30 seconds")
        print("   - User has time to solve manually")
        # captcha.wait_for_captcha_solution(custom_timeout=30)
        
        # Strategy 2: Interactive (wait for Enter key)
        print("\n2. Interactive Strategy")
        print("   - Waits until user presses Enter")
        print("   - Best for ensuring CAPTCHA is actually solved")
        # captcha.wait_for_captcha_interactive()
        
        # Strategy 3: Smart detection
        print("\n3. Smart Detection Strategy")
        print("   - Automatically detects when CAPTCHA is solved")
        print("   - Checks every 2 seconds, max 60s")
        # captcha.wait_for_captcha_smart(check_interval=2, max_wait=60)
        
        print("\n✅ CAPTCHA handler demo complete!")
        
    finally:
        driver.quit()


def demo_integrated_workflow():
    """Demonstrate complete workflow with both features"""
    print("\n" + "="*60)
    print("DEMO: Integrated Workflow")
    print("="*60)
    
    driver = webdriver.Chrome()
    human = HumanBehavior(driver)
    captcha = CaptchaHandler(driver, timeout=30)
    
    try:
        print("\nSimulated job application workflow:\n")
        
        # 1. Navigate to form
        print("1. Navigating to job application...")
        # driver.get("https://example.com/apply")
        HumanBehavior.random_delay(2, 3)
        print("   ✓ Page loaded")
        
        # 2. Fill form fields with delays
        print("\n2. Filling form fields...")
        print("   - First name (with human-like typing)")
        HumanBehavior.random_delay(1, 2)  # Delay between fields
        print("   - Last name")
        HumanBehavior.random_delay(1, 2)
        print("   - Email")
        HumanBehavior.random_delay(1, 2)
        print("   - Phone")
        print("   ✓ Form filled with human-like delays")
        
        # 3. Upload resume
        print("\n3. Uploading resume...")
        HumanBehavior.random_delay(1, 2)
        print("   ✓ Resume uploaded")
        
        # 4. Handle CAPTCHA
        print("\n4. Checking for CAPTCHA...")
        print("   If CAPTCHA detected:")
        print("   - Try automatic solving")
        print("   - If fails, wait 30s for manual solve")
        print("   - Optional: Use 2Captcha API")
        
        # 5. Submit with delay
        print("\n5. Submitting application...")
        HumanBehavior.random_delay(2, 4)  # Think before submitting
        print("   ✓ Application submitted")
        
        print("\n✅ Integrated workflow demo complete!")
        
    finally:
        driver.quit()


if __name__ == "__main__":
    print("\n🤖 HUMAN BEHAVIOR & CAPTCHA HANDLER DEMO\n")
    
    choice = input("""
Choose demo to run:
1. Human Behavior only
2. CAPTCHA Handler only  
3. Integrated Workflow (recommended)
4. Exit

Enter choice (1-4): """)
    
    if choice == "1":
        demo_human_behavior()
    elif choice == "2":
        demo_captcha_handler()
    elif choice == "3":
        demo_integrated_workflow()
    else:
        print("\nExiting...")
