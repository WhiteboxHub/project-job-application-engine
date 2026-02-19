# 🎓 Beginner's Guide: How Insight Global Strategy Works

## 📚 Table of Contents
1. [Big Picture Overview](#big-picture-overview)
2. [The Strategy Pattern](#the-strategy-pattern)
3. [Step-by-Step Walkthrough](#step-by-step-walkthrough)
4. [Key Concepts Explained](#key-concepts-explained)
5. [How to Apply This to Wipro](#how-to-apply-this-to-wipro)

---

## 🎯 Big Picture Overview

### What is a "Strategy"?

A **strategy** is like a recipe for a specific job site. Just like you'd follow different recipes to cook Italian vs Chinese food, each job site needs its own "recipe" for:
- How to search for jobs
- How to fill out application forms
- How to submit applications

### The Flow

```
User runs script
    ↓
Script loads Insight Global strategy
    ↓
Strategy does 2 main things:
    1️⃣ FIND JOBS (search the website)
    2️⃣ APPLY TO JOBS (fill forms and submit)
```

---

## 🏗️ The Strategy Pattern

### Base Class: `BaseStrategy`

Think of this as a **template** that all strategies must follow. It's located in `strategies/base.py`:

```python
class BaseStrategy(ABC):
    def __init__(self, driver, job_site, selectors):
        self.driver = driver        # Chrome browser
        self.job_site = job_site    # Database info about site
        self.selectors = selectors  # CSS selectors for elements
    
    @abstractmethod
    def login(self):
        """Login to the site (if needed)"""
        pass
    
    @abstractmethod
    def find_jobs(self):
        """Search and collect job listings"""
        pass
    
    @abstractmethod
    def apply(self, listing):
        """Apply to one job"""
        pass
```

**Key Point**: Every strategy MUST implement these 3 methods: `login()`, `find_jobs()`, and `apply()`.

### Insight Global Strategy: `InsightGlobalStrategy`

This is the **actual implementation** for Insight Global's website. It inherits from `BaseStrategy`:

```python
class InsightGlobalStrategy(BaseStrategy):
    def __init__(self, driver, job_site, selectors, db_session=None):
        super().__init__(driver, job_site, selectors)  # Call parent
        self.config_data = self._load_config()  # Load your info
        self.human = HumanBehavior(driver)      # Human-like typing
        self.captcha_handler = CaptchaHandler(driver)  # Handle reCAPTCHA
```

---

## 📖 Step-by-Step Walkthrough

### **STEP 1: Initialization** (`__init__`)

```python
def __init__(self, driver, job_site, selectors, db_session=None):
    super().__init__(driver, job_site, selectors)
    self.db_session = db_session
    self.config_data = self._load_config()  # ← Loads guest_form_data.json
    self.human = HumanBehavior(driver)      # ← For realistic typing
    self.captcha_handler = CaptchaHandler(driver, timeout=120)
```

**What happens:**
- Sets up the Chrome browser (`driver`)
- Loads your personal info from `data/guest_form_data.json`
- Creates helper objects for human-like behavior and CAPTCHA handling

---

### **STEP 2: Login** (`login()`)

```python
def login(self):
    """No login required for guest applications"""
    logger.info("InsightGlobal: No login required (guest mode).")
    return True
```

**What happens:**
- Insight Global allows guest applications
- No login needed, so this just returns `True`

---

### **STEP 3: Find Jobs** (`find_jobs()` and `_search_jobs()`)

This is where the magic happens! Let's break it down:

#### 3.1 Navigate to the site
```python
def _search_jobs(self, keyword, location, distance):
    url = "https://insightglobal.com/jobs/"
    logger.info(f"Opening Insight Global: {url}")
    self.driver.get(url)  # ← Opens the website in Chrome
```

#### 3.2 Wait for the page to load
```python
WebDriverWait(self.driver, 15).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='Title']"))
)
```

**Translation**: "Wait up to 15 seconds for the search input field to appear on the page"

#### 3.3 Fill in the search form
```python
# Find the keyword input box
keyword_input = self.driver.find_element(By.CSS_SELECTOR, "#textinput")
keyword_input.clear()
keyword_input.send_keys(keyword)  # ← Type "AI" or whatever keyword
logger.info(f"Entered keyword: {keyword}")
```

**What's happening:**
1. `find_element()` - Finds the search box on the page using CSS selector `#textinput`
2. `.clear()` - Clears any existing text
3. `.send_keys()` - Types your keyword (like "AI Engineer")

#### 3.4 Click the search button
```python
search_btn = self.driver.find_element(By.CSS_SELECTOR, "#homesearch")
search_btn.click()  # ← Clicks the search button
```

#### 3.5 Extract job listings from ALL pages (PAGINATION)
```python
job_urls = []
page = 0

while page < max_pages:
    page += 1
    
    # Get all job listings on current page
    result_rows = self.driver.find_elements(By.CSS_SELECTOR, "div.result")
    
    for row in result_rows:
        # Extract job info from each row
        link = row.find_element(By.CSS_SELECTOR, "div.job-title a")
        href = link.get_attribute('href')  # ← Get the job URL
        title = link.text.strip()          # ← Get the job title
        
        job_urls.append(href)
        logger.info(f"Found job: {title}")
        
        # Save to database
        job_listing = JobListing(
            job_site_id=self.job_site.id,
            external_job_id=job_id,
            job_title=title,
            job_url=href,
            status='discovered'
        )
        self.db_session.add(job_listing)
        self.db_session.commit()
    
    # Try to go to next page
    next_btn = self.driver.find_element(By.XPATH, "//a[@title='Page Forward']")
    next_btn.click()  # ← Click "Next Page"
    time.sleep(3)
```

**Key Concepts:**
- `find_elements()` (plural) - Finds ALL matching elements
- Loop through each job listing
- Extract title and URL from each
- Click "Next" to go to the next page
- Repeat until no more pages

---

### **STEP 4: Apply to Jobs** (`apply()` and `_apply_to_job()`)

Now the bot applies to each job it found:

#### 4.1 Navigate to the job page
```python
def _apply_to_job(self, job_url):
    self.driver.get(job_url)  # ← Open the specific job page
    time.sleep(2)
```

#### 4.2 Click the "Apply" button
```python
apply_btn = self.driver.find_element(By.CSS_SELECTOR, "#ContentPlaceHolder1_lblApplyLink")
apply_btn.click()
logger.info("Clicked Apply button")
```

#### 4.3 Click "Apply as Guest"
```python
guest_link = self.driver.find_element(By.CSS_SELECTOR, "#ContentPlaceHolder1_guestLogin4")
guest_url = guest_link.get_attribute('href')
self.driver.get(guest_url)  # ← Navigate to guest application form
```

#### 4.4 Fill out the form WITH HUMAN-LIKE BEHAVIOR
```python
applicant = self.config_data.get('applicant', {})  # ← Your info from JSON

# First Name - with realistic typing
first_name_input = self.driver.find_element(By.CSS_SELECTOR, "#txtFirstName")
self.human.fill_text_field(first_name_input, applicant.get('first_name', ''))
logger.info(f"Filled first name: {applicant.get('first_name')}")

# Random delay (1-2 seconds) to look human
HumanBehavior.random_delay(1, 2)

# Last Name
last_name_input = self.driver.find_element(By.CSS_SELECTOR, "#txtLastName")
self.human.fill_text_field(last_name_input, applicant.get('last_name', ''))

# Email
email_input = self.driver.find_element(By.CSS_SELECTOR, "#txtEmail")
self.human.fill_text_field(email_input, applicant.get('email', ''))

# Phone
phone_input = self.driver.find_element(By.CSS_SELECTOR, "#txtPhone")
self.human.fill_text_field(phone_input, applicant.get('phone', ''))
```

**Why `self.human.fill_text_field()`?**
- Regular `.send_keys()` types instantly (robot-like ❌)
- `fill_text_field()` types with random delays between characters (human-like ✅)

#### 4.5 Upload Resume
```python
resume_path = self.config_data.get('resume_path', '')  # e.g., "resume/ali_resume.pdf"

# Build full path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
resume_full_path = os.path.join(project_root, resume_path)

# Find file input (usually hidden)
file_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='file']")
file_input.send_keys(resume_full_path)  # ← Sends the file path to upload
logger.info("Resume uploaded")
```

#### 4.6 Handle reCAPTCHA
```python
# Detect if reCAPTCHA is present
if self.captcha_handler.detect_recaptcha():
    logger.warning("⚠️ reCAPTCHA detected - waiting for manual solve...")
    self.captcha_handler.wait_for_manual_solve()  # ← Waits 120 seconds for you to solve
```

#### 4.7 Submit the application
```python
submit_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
submit_btn.click()
logger.info("✅ Application submitted!")

# Update database
csv_tracker.update_job_status('insight_global', job_url, 'applied')
```

---

## 🔑 Key Concepts Explained

### 1. **CSS Selectors** - How to Find Elements

Think of a CSS selector as an "address" to find things on a webpage.

| Selector | What it finds | Example |
|----------|--------------|---------|
| `#id` | Element with specific ID | `#txtFirstName` finds `<input id="txtFirstName">` |
| `.class` | Elements with a class | `.job-title` finds `<div class="job-title">` |
| `tag` | HTML tags | `button` finds all `<button>` elements |
| `[attribute]` | Elements with attribute | `input[type='file']` finds file upload inputs |

**How to find the right selector:**
1. Right-click the element on the webpage
2. Select "Inspect" (opens DevTools)
3. Right-click the highlighted HTML
4. Copy → Copy selector

### 2. **Selenium WebDriver Methods**

| Method | What it does |
|--------|-------------|
| `driver.get(url)` | Navigate to a URL |
| `find_element()` | Find ONE element |
| `find_elements()` | Find ALL matching elements |
| `click()` | Click an element |
| `send_keys(text)` | Type text into an input field |
| `get_attribute('href')` | Get an attribute value (like href, src, etc) |
| `.text` | Get the visible text of an element |

### 3. **Waits** - Why We Need Them

Websites load dynamically with JavaScript. You need to WAIT for elements to appear:

```python
# BAD - might fail if page hasn't loaded yet
button = driver.find_element(By.CSS_SELECTOR, "button")

# GOOD - waits up to 10 seconds for button to appear
button = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "button"))
)
```

### 4. **Database Tracking**

Every job is saved to the database:

```python
job_listing = JobListing(
    job_site_id=self.job_site.id,      # Which site (Insight Global, LanceSoft, etc)
    external_job_id=job_id,             # Job ID from the website
    job_title=title,                    # "AI Engineer"
    job_url=href,                       # Full URL to job posting
    status='discovered'                 # Status: discovered → applied
)
self.db_session.add(job_listing)
self.db_session.commit()
```

Statuses:
- `discovered` - Found the job, haven't applied yet
- `applied` - Successfully submitted application
- `failed` - Application attempt failed

---

## 🚀 How to Apply This to Wipro

Now you understand the pattern! Here's how to implement Wipro:

### **Step 1: Visit Wipro Careers Site**
Open https://careers.wipro.com/ in Chrome

### **Step 2: Find the Selectors**

Use Chrome DevTools to find the CSS selectors for:

1. **Search form:**
   - Keyword input box
   - Location input box
   - Search button

2. **Job listings:**
   - Container for each job (probably `<div>` or `<li>`)
   - Job title element
   - Job link/URL
   - Job ID

3. **Application form:**
   - Apply button
   - First name input
   - Last name input
   - Email input
   - Phone input
   - Resume upload input
   - Submit button

### **Step 3: Update `_load_selectors()` in wipro.py**

Replace the template selectors with the real ones you found:

```python
def _load_selectors(self):
    return {
        # Use ACTUAL selectors from Wipro website
        'keyword_input': "#actual-wipro-keyword-input",  # ← UPDATE THIS
        'location_input': "#actual-wipro-location-input",  # ← UPDATE THIS
        'search_button': "button.actual-wipro-search-btn",  # ← UPDATE THIS
        # ... etc
    }
```

### **Step 4: Test with Dry-Run**

```bash
python scripts/main.py --site "Wipro" --dry-run
```

Watch the browser to see if it:
- ✅ Fills in the search form correctly
- ✅ Finds job listings
- ✅ Opens a job application
- ✅ Fills in your info

### **Step 5: Fix Any Issues**

If something doesn't work:
1. Check the terminal logs - they'll tell you which selector failed
2. Re-inspect that element on Wipro's site
3. Update the selector in `_load_selectors()`
4. Try again

---

## 💡 Pro Tips

1. **Start Simple**: Get job search working first, then worry about applications
2. **Use Console**: Test selectors in Chrome console first:
   ```javascript
   document.querySelector("#textinput")  // Test if selector works
   ```
3. **Watch the Browser**: Run in non-headless mode to SEE what's happening
4. **Check Logs**: The terminal output tells you exactly what's happening

---

## 📝 Summary

The Insight Global strategy:
1. **Opens** the Insight Global careers page
2. **Fills** the search form with your keywords
3. **Clicks** search and waits for results
4. **Loops** through all pages, collecting job URLs
5. **Saves** each job to the database
6. **Opens** each job application page
7. **Fills** the form with your info (name, email, phone)
8. **Uploads** your resume
9. **Handles** reCAPTCHA if present
10. **Submits** the application

**Your Wipro strategy will do EXACTLY THE SAME THING**, just with different CSS selectors!

---

🎉 **You've got this!** The hard part (understanding the pattern) is done. Now it's just a matter of finding the right selectors for Wipro.
