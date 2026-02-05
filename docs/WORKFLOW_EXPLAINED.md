# Multi-Location Job Search Workflow

## ✅ Fixed Issue

**Problem**: Missing `random` import causing error: `name 'random' is not defined`

**Solution**: Added `import random` to `strategies/custom/insight_global.py`

---

## 🔄 How the Multi-Location Search Works

### Workflow Overview

```
1. START
   ↓
2. Search Location 1 + Keyword 1 → Collect jobs
   ↓
3. Wait 2-4 seconds (avoid rate limit)
   ↓
4. Search Location 2 + Keyword 1 → Collect jobs
   ↓
5. Wait 2-4 seconds
   ↓
... (continue for all 20 combinations)
   ↓
20. Search Location 4 + Keyword 5 → Collect jobs
   ↓
21. DEDUPLICATE all collected jobs
   ↓
22. Display search summary
   ↓
23. Apply to Job 1
   ↓
24. Wait (cooldown period)
   ↓
25. Apply to Job 2
   ↓
... (continue for all unique jobs)
   ↓
N. Final summary
   ↓
STOP browser
```

---

## 📊 Detailed Execution Flow

### Phase 1: Job Search (All 20 Locations)

```python
# This happens in find_jobs() method

for each search_configuration in search_configurations:
    1. Navigate to https://insightglobal.com/jobs/
    2. Fill keyword (e.g., "Data Scientist")
    3. Fill location (e.g., "California, MO")
    4. Set distance (50 miles)
    5. Click search button
    6. Extract all job URLs from results
    7. Save to list
    8. Wait 2-4 seconds ← Prevents rate limiting
    
    # Repeat for next combination
```

**Expected Console Output:**
```
Found 20 search configurations to process

============================================================
Search 1/20
Keyword: 'Data Engineer Data Scientist', Location: 'California, MO', Distance: 50 miles
============================================================
Opening Insight Global: https://insightglobal.com/jobs/
Search page loaded successfully
Entered keyword: Data Engineer Data Scientist
Entered location: California, MO
Set distance: 50 miles
Clicked search button
Found 3 job results
Found job: Senior Data Engineer
Found job: Data Scientist - Remote
Found job: ML Engineer
Waiting 3.2 seconds before next search...

============================================================
Search 2/20
Keyword: 'Data Engineer Data Scientist', Location: 'California City, CA', Distance: 50 miles
============================================================
... (continues for all 20 searches)

============================================================
SEARCH SUMMARY
Total searches performed: 20
Total jobs found: 45
Unique jobs: 38
Duplicates removed: 7
============================================================
```

---

### Phase 2: Deduplication

```python
# Remove duplicate job URLs while preserving order

unique_urls = []
seen = set()

for url in all_job_urls:
    if url not in seen:
        seen.add(url)
        unique_urls.append(url)
```

**Why This Matters:**
- Same job may appear in multiple location searches
- Prevents applying to the same job twice

---

### Phase 3: Application Process

```python
# This happens in run_search_and_apply() method

for each unique job:
    1. Navigate to job detail page
    2. Click "Apply" button
    3. Click "Apply as Guest"
    4. Fill form with human-like delays:
       - First name (with typing delay)
       - Wait 1-2 seconds
       - Last name (with typing delay)
       - Wait 1-2 seconds
       - Email (with typing delay)
       - Wait 1-2 seconds
       - Phone (with typing delay)
       - Wait 1-2 seconds
    5. Upload resume
    6. Handle CAPTCHA (30-second wait if present)
    7. Wait 2-4 seconds (think before submit)
    8. Click Submit button
    9. Wait cooldown period (30 seconds default)
    
    # Repeat for next job
```

**Expected Console Output:**
```
============================================================
Found 38 jobs - starting application process
============================================================

--- Processing job 1/38 ---
Applying to job: https://insightglobal.com/jobs/12345/...
Navigating to guest application form...
Guest application form loaded

📝 Filling form fields with human-like behavior...
Filled first name: GHAZAL
Filled last name: SULTAN
Filled email: ghazal.sultan1616@gmail.com
Filled phone: +1 (669) 213-3034
✅ Selected 'Yes' for minimum requirements

📎 RESUME UPLOAD STARTING
File path: C:\...\resume\Ghazal_Sultan.pdf
✅ RESUME UPLOAD SUCCESSFUL!

🔍 Checking for reCAPTCHA...
⚠️ reCAPTCHA detected on this form
[If CAPTCHA present: 30-second countdown appears]

📤 Submitting application...
✅ SUBMITTED APPLICATION!

Waiting 30 seconds before next job...

--- Processing job 2/38 ---
... (continues for all jobs)

============================================================
APPLICATION RUN COMPLETE
Successfully processed: 38/38 jobs
============================================================
```

---

## ⏱️ Time Breakdown

### Search Phase
- **Per search**: ~10-15 seconds
- **Delay between searches**: 2-4 seconds (avg 3s)
- **Total for 20 searches**: (15s × 20) + (3s × 19) = 300s + 57s = **~6 minutes**

### Application Phase  
- **Per application** (no CAPTCHA): ~15-20 seconds
- **Per application** (with CAPTCHA): ~45-50 seconds
- **Cooldown between apps**: 30 seconds (default)
- **Total for 38 jobs** (example): (20s + 30s) × 38 = **~32 minutes**

**Total estimated time**: 6 min (search) + 32 min (apply) = **~38 minutes** for 38 jobs

---

## 🎯 Configuration Settings

### Search Distance
Each search uses a **50-mile radius** from the location.

You can change this in `data/guest_form_data.json`:
```json
{
    "keyword": "Data Scientist",
    "location": "California, MO",
    "distance": 100  ← Change to 100 miles
}
```

### Cooldown Between Applications
Default: 30 seconds

Change in `.env`:
```
SUBMISSION_COOLDOWN_SECONDS=60
```

### Max Applications Per Run
Default: No limit (applies to all found jobs)

Change in `.env`:
```
MAX_APPLICATIONS_PER_RUN=10
```

---

## 📝 Your Current Configuration

**Search Matrix**: 5 keywords × 4 locations = **20 searches**

| # | Keyword | Location |
|---|---------|----------|
| 1 | Data Engineer Data Scientist | California, MO |
| 2 | Data Engineer Data Scientist | California City, CA |
| 3 | Data Engineer Data Scientist | California, KY |
| 4 | Data Engineer Data Scientist | California Mens Colony Slo, CA |
| 5 | Data Scientist | California, MO |
| 6 | Data Scientist | California City, CA |
| 7 | Data Scientist | California, KY |
| 8 | Data Scientist | California Mens Colony Slo, CA |
| 9 | Data Scientist Business Data Analyst | California, MO |
| 10 | Data Scientist Business Data Analyst | California City, CA |
| 11 | Data Scientist Business Data Analyst | California, KY |
| 12 | Data Scientist Business Data Analyst | California Mens Colony Slo, CA |
| 13 | AI Engineer | California, MO |
| 14 | AI Engineer | California City, CA |
| 15 | AI Engineer | California, KY |
| 16 | AI Engineer | California Mens Colony Slo, CA |
| 17 | Data Scientist ML Engineer -REMOTE | California, MO |
| 18 | Data Scientist ML Engineer -REMOTE | California City, CA |
| 19 | Data Scientist ML Engineer -REMOTE | California, KY |
| 20 | Data Scientist ML Engineer -REMOTE | California Mens Colony Slo, CA |

**Applicant**: GHAZAL SULTAN  
**Resume**: `resume/Ghazal_Sultan.pdf` ✅

---

## 🚀 Running the Automation

### Test Mode (Dry Run)
```bash
python scripts/main.py --dry-run
```

**What it does:**
- ✅ Searches all 20 locations
- ✅ Shows all jobs found
- ✅ Fills out forms
- ❌ Does NOT submit applications
- Good for testing and verification

### Live Mode
```bash
python scripts/main.py
```

**What it does:**
- ✅ Searches all 20 locations
- ✅ Shows all jobs found
- ✅ Fills out forms
- ✅ **SUBMITS applications**
- Uses human-like delays
- Handles CAPTCHAs (30-second window)

---

## ✅ What Was Fixed

**Error**: `name 'random' is not defined`

**Fix**: Added `import random` to the imports in `strategies/custom/insight_global.py`

**Now the workflow is:**
1. ✅ Search ALL 20 location/keyword combinations
2. ✅ Collect all job URLs
3. ✅ Remove duplicates
4. ✅ Show search summary
5. ✅ Apply to each unique job
6. ✅ Browser closes automatically when done

---

## 💡 Tips

### Monitor Progress
- Watch the console output to see which search/job is being processed
- The summary shows total vs unique jobs
- Each application shows status (success/failed)

### If Searches Find No Jobs
- Try increasing the distance radius
- Try different keyword variations
- Some locations may not have matching jobs

### Stopping Mid-Run
- Press `Ctrl+C` to stop
- Already submitted applications are tracked in CSV
- Can restart and it will skip already-applied jobs

---

## 📊 Expected Behavior Summary

| Phase | What Happens | Duration |
|-------|-------------|----------|
| **Startup** | Load config, start browser | ~10s |
| **Search Phase** | 20 searches with delays | ~6 min |
| **Deduplication** | Remove duplicate jobs | <1s |
| **Summary** | Display search results | <1s |
| **Application Phase** | Apply to all unique jobs | ~30-45 min* |
| **Shutdown** | Close browser, save data | ~5s |

*Depends on number of jobs and CAPTCHAs encountered

---

## 🎉 You're All Set!

The system will now:
1. Search all 20 combinations automatically
2. Collect all unique jobs
3. Apply to each one with human-like behavior
4. Handle CAPTCHAs with 30-second solve window
5. Stop browser when complete

Ready to run! 🚀
