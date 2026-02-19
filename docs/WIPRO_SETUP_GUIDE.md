# Wipro Strategy Setup Guide

## ✅ Created Files

- **`strategies/custom/wipro.py`** - Complete Wipro job application automation strategy

## 📋 Next Steps to Use Wipro Strategy

### 1. Add Wipro to Database

You need to add Wipro as a job site in your DuckDB database. Run this SQL:

```sql
-- Add Wipro ATS Platform (if not exists)
INSERT INTO ats_platforms (name, class_handler) 
VALUES ('Wipro Custom', 'strategies.custom.wipro.WiproStrategy');

-- Add Wipro Job Site
INSERT INTO job_sites (
    company_name, 
    domain, 
    platform_id, 
    is_active,
    search_url_template
) 
VALUES (
    'Wipro', 
    'wipro.com', 
    (SELECT id FROM ats_platforms WHERE name = 'Wipro Custom'),
    true,
    'https://careers.wipro.com/careers-home/'
);
```

### 2. Update Wipro URL

The template uses a generic Wipro careers URL. Update the actual URL in:
- Database: `job_sites.search_url_template` column
- Or in the code: `wipro.py` line 44

### 3. Customize CSS Selectors

The selectors in `wipro.py` are **TEMPLATE examples**. You need to:

1. **Open Wipro careers portal in browser**
2. **Right-click elements → Inspect**
3. **Copy actual CSS selectors/XPaths**
4. **Update the `_load_selectors()` method** (lines 69-125)

Key selectors to update:
- Search form fields
- Job listing containers
- Apply button
- Form input fields
- Submit button

### 4. Test the Strategy

Run in dry-run mode first:

```bash
python scripts/main.py --site "Wipro" --dry-run
```

### 5. Run Live

Once selectors are verified:

```bash
python scripts/main.py --site "Wipro"
```

## 🎯 Key Features Included

✅ **Job Discovery** - Scrapes Wipro job listings with pagination  
✅ **Human-Like Behavior** - Random delays and natural typing  
✅ **Resume Upload** - Automatic file upload with verification  
✅ **reCAPTCHA Handling** - Detects and waits for manual solve  
✅ **Database Tracking** - Saves jobs and applications to DuckDB  
✅ **CSV Backup** - Fallback tracking in CSV files  
✅ **Error Handling** - Robust error recovery  
✅ **Dry-Run Mode** - Test without actually submitting  

## ⚙️ Configuration

Update `data/guest_form_data.json` for Wipro-specific searches:

```json
{
    "search": {
        "keyword": "Software Engineer",
        "location": "Bangalore"
    },
    "applicant": {
        "first_name": "Your Name",
        "last_name": "Your Last Name",
        "email": "your.email@example.com",
        "phone": "+1 (XXX) XXX-XXXX"
    },
    "resume_path": "resume/your_resume.pdf"
}
```

## 🔍 Troubleshooting

### Selectors Not Working?
- **Cause**: Wipro changed their website structure
- **Fix**: Re-inspect elements and update selectors in `_load_selectors()`

### Jobs Not Found?
- **Cause**: Wrong job container selector
- **Fix**: Update `job_container` selector

### Application Not Submitting?
- **Cause**: Submit button selector incorrect
- **Fix**: Inspect submit button and update `submit_button` selector

## 📝 Notes

- This strategy follows the same pattern as `InsightGlobalStrategy` and `LanceSoftStrategy`
- All methods inherit from `BaseStrategy` abstract class
- Supports both single-phase (immediate apply) and two-phase (collect then apply) workflows
- Currently implements two-phase approach via `find_jobs()` and `apply()` methods

---

**Ready to customize for your specific Wipro portal!** 🚀
