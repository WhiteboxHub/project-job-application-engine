# Multi-Location & Multi-Keyword Job Search Configuration

## Summary

Your job application automation is now configured to search **20 different combinations** of job titles and locations.

---

## 📍 Search Locations (4 locations)

1. **California, MO** - Missouri
2. **California City, CA** - California  
3. **California, KY** - Kentucky
4. **California Mens Colony Slo, CA** - California (San Luis Obispo)

---

## 💼 Job Titles/Keywords (5 keywords)

1. **Data Engineer Data Scientist**
2. **Data Scientist**
3. **Data Scientist Business Data Analyst**
4. **AI Engineer**
5. **Data Scientist ML Engineer -REMOTE**

---

## 🔄 Total Search Combinations

**5 keywords × 4 locations = 20 searches**

Each search uses a **50-mile radius** from the specified location.

---

## 👤 Applicant Information

- **Name**: GHAZAL SULTAN
- **Email**: ghazal.sultan1616@gmail.com
- **Phone**: +1 (669) 213-3034
- **Resume**: `resume/Ghazal_Sultan.pdf` ✅ (Verified)

---

## 📋 Full Search Matrix

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

---

## 🚀 How It Works

### Automated Search Process

1. **Load Configuration**: Reads `data/guest_form_data.json`
2. **Multiple Searches**: Performs 20 separate job searches
3. **Deduplication**: Removes duplicate job listings
4. **Rate Limiting**: 2-4 second delay between searches
5. **Apply to Jobs**: Applies to each unique job found

### What You'll See

```
Found 20 search configurations to process

============================================================
Search 1/20
Keyword: 'Data Engineer Data Scientist', Location: 'California, MO', Distance: 50 miles
============================================================
... (searches for jobs)
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

## ⚙️ Configuration Files

### Main Configuration
**File**: `data/guest_form_data.json`

```json
{
    "search_configurations": [
        {
            "keyword": "Data Engineer Data Scientist",
            "location": "California, MO"
        },
        ...
    ],
    "applicant": {
        "first_name": "GHAZAL",
        "last_name": "SULTAN",
        ...
    },
    "resume_path": "resume/Ghazal_Sultan.pdf"
}
```

---

## 🎯 Run Your Job Search

### Dry Run (Test Mode)
```bash
python scripts/main.py --dry-run
```
- Searches all 20 combinations
- Fills out forms
- **Does NOT submit** applications
- Good for testing

### Live Run (Submit Applications)
```bash
python scripts/main.py
```
- Searches all 20 combinations
- Fills out forms
- **Submits applications**
- Uses human-like delays

---

## 📊 Expected Behavior

### Search Phase
- Performs 20 separate searches
- Each search takes ~10-15 seconds
- Total search time: ~4-7 minutes
- Finds and deduplicates job listings

### Application Phase
- Applies to each unique job found
- Human-like delays (1-2s between fields)
- 30-second CAPTCHA wait if needed
- Tracks applications in CSV

---

## ⏱️ Time Estimates

**Search Phase Only**:
- 20 searches × ~15 seconds = ~5 minutes
- Plus 2-4 second delays between searches = ~6-7 minutes total

**Per Application**:
- Form filling: 10-15 seconds (with human delays)
- With CAPTCHA: +30 seconds
- Total per job: 10-45 seconds

**Example Full Run** (if 30 jobs found):
- Search: ~7 minutes
- Applications: 30 jobs × ~20 seconds = ~10 minutes
- **Total: ~17 minutes**

---

## 🔧 Customization Options

### Add More Locations
Edit `data/guest_form_data.json` and add to `search_configurations`:
```json
{
    "keyword": "Data Scientist",
    "location": "New York, NY"
}
```

### Add More Keywords
Add new keyword with all locations:
```json
{
    "keyword": "Machine Learning Engineer",
    "location": "California, MO"
}
```

### Change Search Radius
Modify the `distance` field:
```json
{
    "keyword": "Data Scientist",
    "location": "California, MO",
    "distance": 100
}
```

---

## 📝 What Was Changed

### 1. Configuration File
- **File**: `data/guest_form_data.json`
- **Change**: Added `search_configurations` array with 20 searches
- **Resume**: Updated to `Ghazal_Sultan.pdf`
- **Applicant**: Updated with Ghazal Sultan's information

### 2. Strategy Code
- **File**: `strategies/custom/insight_global.py`
- **Change**: Enhanced `find_jobs()` method to:
  - Support multiple search configurations
  - Perform searches in sequence with delays
  - Remove duplicate jobs
  - Display search summary

---

## ✅ Ready to Use

Everything is configured and ready! Your next run will:

1. ✅ Search 20 different keyword/location combinations
2. ✅ Find all matching jobs
3. ✅ Remove duplicates
4. ✅ Apply to each job with Ghazal Sultan's information
5. ✅ Use the correct resume: `Ghazal_Sultan.pdf`
6. ✅ Use human-like behavior (delays, natural typing)
7. ✅ Handle CAPTCHAs with 30-second solve window

**Start your job search:**
```bash
# Test first
python scripts/main.py --dry-run

# Then run live
python scripts/main.py
```

Good luck with your job search! 🚀
