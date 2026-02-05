# Human-Like Behavior & CAPTCHA Handling Guide

This guide explains how to use the new human behavior simulation and CAPTCHA handling features in your job application automation.

## 📚 Table of Contents

1. [Overview](#overview)
2. [Human Behavior Features](#human-behavior-features)
3. [CAPTCHA Handling](#captcha-handling)
4. [Integration Examples](#integration-examples)
5. [Configuration](#configuration)

---

## Overview

The automation now includes two powerful modules to make form filling more realistic and handle CAPTCHA challenges:

- **`core/human_behavior.py`**: Simulates human-like interactions (typing, delays, scrolling)
- **`core/captcha_handler.py`**: Handles CAPTCHA challenges with multiple strategies

---

## Human Behavior Features

### Random Delays

Simulate natural thinking/reading time between actions:

```python
from core.human_behavior import HumanBehavior

# Random delay between 1-3 seconds
HumanBehavior.random_delay(1, 3)

# Longer delay (2-5 seconds)
HumanBehavior.random_delay(2, 5)
```

**Recommended Delays:**
- Between form fields: `1-2 seconds`
- After page load: `2-4 seconds`
- Before submission: `2-4 seconds`
- After file upload: `2-3 seconds`

### Human-Like Typing

Type text with natural keystroke delays (50-150ms per character):

```python
from selenium.webdriver.common.by import By

driver = webdriver.Chrome()
human = HumanBehavior(driver)

# Find input element
email_field = driver.find_element(By.ID, "email")

# Type with human-like delays
human.human_type(email_field, "john.doe@example.com")
```

### Fill Text Fields

Complete workflow for filling text fields:

```python
# Automatically: scroll to element, click, clear, type, wait
first_name = driver.find_element(By.ID, "firstName")
human.fill_text_field(first_name, "John")
```

This method:
1. Scrolls element into view
2. Clicks on the field
3. Clears existing text
4. Types with human-like delays
5. Waits randomly (0.5-1.5s) after filling

### Smooth Scrolling

```python
# Scroll to specific element
element = driver.find_element(By.ID, "submit-btn")
human.scroll_to_element(element, smooth=True)

# Scroll page by pixels
human.scroll_page(direction='down', amount=500)
human.scroll_page(direction='up', amount=300)
```

### Human-Like Clicking

Click with mouse movement and delays:

```python
button = driver.find_element(By.ID, "apply-btn")
human.human_click(button)
```

---

## CAPTCHA Handling

### Three Strategies

#### 1. Countdown Strategy (Default: 30 seconds)

**Best for:** Consistent automation with minimal user interaction

```python
from core.captcha_handler import CaptchaHandler

captcha = CaptchaHandler(driver, timeout=30)

# Wait 30 seconds for user to solve
captcha.wait_for_captcha_solution()

# Custom timeout
captcha.wait_for_captcha_solution(custom_timeout=60)
```

**What happens:**
- Displays countdown timer
- User has 30 seconds to solve CAPTCHA manually
- Automatically proceeds after timeout

#### 2. Interactive Strategy

**Best for:** Ensuring CAPTCHA is actually solved

```python
# Wait indefinitely until user presses Enter
captcha.wait_for_captcha_interactive()
```

**What happens:**
- Waits for user to press Enter key
- No timeout - full control
- Best for complex CAPTCHAs

#### 3. Smart Detection Strategy

**Best for:** Automatic detection when CAPTCHA is solved

```python
# Check every 2 seconds, max 60 seconds
captcha.wait_for_captcha_smart(check_interval=2, max_wait=60)
```

**What happens:**
- Periodically checks if CAPTCHA is solved
- Automatically proceeds when checkmark detected
- Falls back after max timeout

### Complete CAPTCHA Workflow

```python
# 1. Initialize handler with 30-second timeout
captcha_handler = CaptchaHandler(driver, timeout=30)

# 2. Check for CAPTCHA
from selenium.webdriver.common.by import By

recaptcha_frames = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha']")

if recaptcha_frames:
    print("CAPTCHA detected!")
    
    # Step 1: Try automatic solving (if you have auto-click implemented)
    # success = attempt_auto_solve()
    
    # Step 2: If auto-solve fails, wait for manual solution
    captcha_handler.wait_for_captcha_solution(custom_timeout=30)
    
    # Optional Step 3: Use 2Captcha API (if configured)
    # solve_with_2captcha()
```

---

## Integration Examples

### Example 1: Simple Form Filling

```python
from core.human_behavior import HumanBehavior
from selenium import webdriver
from selenium.webdriver.common.by import By

driver = webdriver.Chrome()
human = HumanBehavior(driver)

# Navigate to form
driver.get("https://example.com/apply")
HumanBehavior.random_delay(2, 3)  # Wait for page load

# Fill form with human-like behavior
first_name = driver.find_element(By.ID, "firstName")
human.fill_text_field(first_name, "John")
HumanBehavior.random_delay(1, 2)  # Delay between fields

last_name = driver.find_element(By.ID, "lastName")
human.fill_text_field(last_name, "Doe")
HumanBehavior.random_delay(1, 2)

email = driver.find_element(By.ID, "email")
human.fill_text_field(email, "john.doe@email.com")
HumanBehavior.random_delay(1, 2)

# Submit with delay
submit_btn = driver.find_element(By.ID, "submit")
HumanBehavior.random_delay(2, 4)  # Think before submitting
human.human_click(submit_btn)
```

### Example 2: Job Application with CAPTCHA

```python
from core.human_behavior import HumanBehavior
from core.captcha_handler import CaptchaHandler
from selenium import webdriver
from selenium.webdriver.common.by import By

driver = webdriver.Chrome()
human = HumanBehavior(driver)
captcha = CaptchaHandler(driver, timeout=30)

# Navigate and fill form
driver.get("https://jobsite.com/apply")
HumanBehavior.random_delay(2, 3)

# Fill all fields with delays
fields = {
    "#firstName": "John",
    "#lastName": "Doe",
    "#email": "john@email.com",
    "#phone": "555-1234"
}

for selector, value in fields.items():
    element = driver.find_element(By.CSS_SELECTOR, selector)
    human.fill_text_field(element, value)
    HumanBehavior.random_delay(1, 2)  # Delay between fields

# Check for CAPTCHA
recaptcha = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha']")
if recaptcha:
    print("CAPTCHA detected - waiting 30 seconds for manual solve...")
    captcha.wait_for_captcha_solution(custom_timeout=30)

# Submit application
submit = driver.find_element(By.ID, "submit")
HumanBehavior.random_delay(2, 4)
human.human_click(submit)

print("Application submitted!")
driver.quit()
```

### Example 3: Using in InsightGlobalStrategy

The integration is already done! The `InsightGlobalStrategy` class now uses:

```python
class InsightGlobalStrategy(BaseStrategy):
    def __init__(self, driver, db_session, config):
        super().__init__(driver, db_session, config)
        # Automatically initialized
        self.human = HumanBehavior(driver)
        self.captcha_handler = CaptchaHandler(driver, timeout=30)
```

**How it works:**
1. Form fields are filled with human-like typing
2. 1-2 second delays between each field
3. Smooth scrolling to elements
4. CAPTCHA gets 30-second manual solve window
5. 2-4 second delay before clicking submit button

---

## Configuration

### Customizing Delay Times

Edit the delays in your strategy file:

```python
# Short delays (faster automation)
HumanBehavior.random_delay(0.5, 1)

# Medium delays (default - balanced)
HumanBehavior.random_delay(1, 2)

# Long delays (more human-like)
HumanBehavior.random_delay(2, 4)
```

### CAPTCHA Timeout

Set default timeout when creating handler:

```python
# 30 seconds (default)
captcha = CaptchaHandler(driver, timeout=30)

# 60 seconds
captcha = CaptchaHandler(driver, timeout=60)

# Or override per-call
captcha.wait_for_captcha_solution(custom_timeout=45)
```

### 2Captcha API (Optional)

Add to your `.env` file:

```bash
TWOCAPTCHA_API_KEY=your_api_key_here
```

Install the library:

```bash
pip install 2captcha-python
```

The system will automatically use 2Captcha as fallback if:
- Automatic CAPTCHA click fails
- API key is configured
- Not in dry-run mode

---

## Best Practices

### ✅ Do's

- **Use random delays between form fields** (1-2 seconds)
- **Add longer delays before critical actions** (submitting, confirming)
- **Let CAPTCHA handler manage the wait** (don't manually add time.sleep)
- **Test in dry-run mode first** to verify delays feel natural

### ❌ Don'ts

- **Don't use fixed delays** - always use random ranges
- **Don't make delays too short** (\< 0.5s looks robotic)
- **Don't skip CAPTCHA wait** - rushing causes failures
- **Don't use same delay values everywhere** - vary them naturally

### Recommended Delay Patterns

```python
# Page navigation
driver.get(url)
HumanBehavior.random_delay(2, 4)

# Between form fields
HumanBehavior.random_delay(1, 2)

# After file upload
HumanBehavior.random_delay(2, 3)

# Before clicking submit
HumanBehavior.random_delay(2, 4)

# After form submission
HumanBehavior.random_delay(3, 5)
```

---

## Troubleshooting

### Form Fields Not Filling
- Increase initial page load delay
- Check if element selectors are correct
- Verify elements are visible and enabled

### CAPTCHA Not Being Detected
- Check iframe selector: `iframe[src*='recaptcha']`
- Verify CAPTCHA loads before check
- Try increasing smart detection `max_wait`

### Delays Too Fast/Slow
- Adjust min/max values in `random_delay()` calls
- Test different ranges to find natural timing
- Consider network speed in your delays

---

## Summary

**Key Features Implemented:**

✅ Human-like typing with variable speed (50-150ms per char)  
✅ Random delays between actions (configurable)  
✅ Smooth scrolling to elements  
✅ Natural mouse movements and clicks  
✅ 30-second CAPTCHA wait time (default)  
✅ Three CAPTCHA handling strategies  
✅ Full integration with existing automation  

**Run Your Automation:**

```bash
# Dry run (test without submitting)
python scripts/main.py --dry-run

# Live mode with human-like behavior
python scripts/main.py
```

---

## Need Help?

- Check the example script: `examples/human_behavior_demo.py`
- Review the source code: `core/human_behavior.py` and `core/captcha_handler.py`
- Test individual features before running full automation
