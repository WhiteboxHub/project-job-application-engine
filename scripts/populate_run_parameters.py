"""
Auto-populate run_parameters for active candidates in candidate_marketing table

This script:
1. Fetches candidates from candidate_marketing (filtered by ID or flag)
2. Gets candidate details from candidate table
3. Downloads/reads resume from resume_url
4. Parses resume PDF to JSON
5. Builds run_parameters JSON
6. Updates candidate_marketing table

Usage:
    python scripts/populate_run_parameters.py --candidate-id 533
    python scripts/populate_run_parameters.py --flagged-only   # Default behavior
    python scripts/populate_run_parameters.py --all            # Process EVERYONE (use with caution)
"""
import mysql.connector
from mysql.connector import Error
import json
import os
import sys
import requests
import argparse
import PyPDF2
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from scripts.parse_resume import parse_resume as robust_parse_resume

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text
    except Exception as e:
        print(f"      Error extracting PDF text: {e}")
        return ""

def parse_resume_simple(text):
    """
    Simple resume parser - extracts basic info from text
    For production, use libraries like pyresparser or custom NLP
    """
    parsed = {
        "skills": [],
        "education": []
    }
    
    # Extract skills (basic keyword matching)
    skill_keywords = [
        "Python", "Java", "JavaScript", "C++", "SQL", "NoSQL",
        "Machine Learning", "AI", "Artificial Intelligence", "Deep Learning",
        "TensorFlow", "PyTorch", "Keras", "Scikit-learn",
        "AWS", "Azure", "GCP", "Docker", "Kubernetes",
        "React", "Angular", "Vue", "Node.js", "Django", "Flask",
        "Data Science", "Data Analysis", "Big Data", "Spark", "Hadoop"
    ]
    
    for skill in skill_keywords:
        if skill.lower() in text.lower():
            parsed["skills"].append(skill)
    
    # Extract education (look for degree keywords)
    education_keywords = ["Bachelor", "Master", "PhD", "B.S.", "M.S.", "MBA", "B.Tech", "M.Tech"]
    for keyword in education_keywords:
        if keyword in text:
            # Extract surrounding context
            pattern = rf"({keyword}[^\n]{{0,100}})"
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                parsed["education"].extend(matches[:3])  # Limit to 3
    
    return parsed

def download_resume(url, save_path):
    """Download resume from URL"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        
        return True
    except Exception as e:
        print(f"      Error downloading resume: {e}")
        return False

def get_db_connection():
    return mysql.connector.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME
    )

def populate_run_parameters(candidate_id=None, flagged_only=True, process_all=False):
    try:
        connection = get_db_connection()
        
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            
            print("=" * 80)
            print("🔄 AUTO-POPULATING RUN_PARAMETERS")
            print("=" * 80)
            
            # Base query
            query = """
                SELECT 
                    cm.id as cm_id,
                    cm.candidate_id,
                    cm.marketing_flag,
                    cm.resume_url,
                    cm.status,
                    c.full_name,
                    c.email,
                    c.phone,
                    c.address,
                    c.zip_code
                FROM candidate_marketing cm
                JOIN candidate c ON cm.candidate_id = c.id
                WHERE cm.status = 'active'
            """
            
            filters = []
            params = []
            
            # 1. Filter by specific candidate ID
            if candidate_id:
                filters.append("cm.candidate_id = %s")
                params.append(candidate_id)
                print(f"👉 Target: Candidate ID {candidate_id}")
            
            # 2. Filter by marketing_flag=1 (default unless process_all is True)
            elif flagged_only and not process_all:
                filters.append("cm.marketing_flag = 1")
                print("👉 Target: Flagged candidates only (marketing_flag = 1)")
            
            # 3. Process everyone (dangerous but useful for init)
            elif process_all:
                print("⚠ Target: ALL active candidates")
            
            if filters:
                query += " AND " + " AND ".join(filters)
            
            cursor.execute(query, tuple(params))
            candidates = cursor.fetchall()
            
            if not candidates:
                print("❌ No matching candidates found.")
                return

            print(f"📋 Found {len(candidates)} candidate(s) to process")
            print("=" * 80)
            
            # Create temp directory for resumes
            temp_dir = "temp_resumes"
            os.makedirs(temp_dir, exist_ok=True)
            
            # Standard search keywords (same for all)
            search_keywords = ["AI", "GEN AI", "AIML", "DATA SCIENTIST", "python"]
            
            success_count = 0
            error_count = 0
            
            for idx, candidate in enumerate(candidates, 1):
                try:
                    print(f"[{idx}/{len(candidates)}] Processing: {candidate['full_name']} (ID: {candidate['candidate_id']})")
                    
                    # Parse name
                    name_parts = candidate['full_name'].split() if candidate['full_name'] else ["", ""]
                    first_name = name_parts[0] if len(name_parts) > 0 else ""
                    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
                    
                    # Build location from candidate data
                    # User requested to default to "USA" to avoid parsing errors like "500056, United"
                    location = "USA"
                    
                    # Optional: Basic check if address explicitly mentions another known country, 
                    # but for now, we force USA as requested to fix the URL issue.
                    if candidate.get('address'):
                        addr_lower = candidate['address'].lower()
                        if "india" in addr_lower:
                            location = "India"
                        elif "canada" in addr_lower:
                            location = "Canada"
                        elif "uk" in addr_lower or "united kingdom" in addr_lower:
                            location = "UK"
                        # Default remains USA for "United States", "US", or empty/unknown addresses
                    
                    # Parse resume
                    parsed_resume = {}
                    resume_path = None
                    
                    if candidate.get('resume_url'):
                        # Check if it's a local file or URL
                        if candidate['resume_url'].startswith('http'):
                            filename = f"resume_{candidate['candidate_id']}.pdf"
                            resume_path = os.path.join(temp_dir, filename)
                            
                            print(f"   ⬇ Downloading resume...")
                            if download_resume(candidate['resume_url'], resume_path):
                                try:
                                    parsed_resume = robust_parse_resume(resume_path)
                                    print(f"      ✓ Parsed: {len(parsed_resume.get('skills', []))} skills, {len(parsed_resume.get('education', []))} education entries")
                                except Exception as e:
                                    print(f"      ⚠ Parse failed: {e}")
                            else:
                                print(f"      ⚠ Download failed")
                        else:
                            # Local file path
                            if os.path.exists(candidate['resume_url']):
                                # Determine if it's PDF or something else (simplified for now)
                                if candidate['resume_url'].lower().endswith('.pdf'):
                                    try:
                                        resume_path = candidate['resume_url']
                                        parsed_resume = robust_parse_resume(resume_path)
                                        print(f"      ✓ Parsed local PDF")
                                    except Exception as e:
                                        print(f"      ⚠ Parse failed: {e}")
                    
                    # Parse address more intelligently
                    raw_address = candidate.get('address', '')
                    parts = [p.strip() for p in raw_address.split(',') if p.strip()]
                    street_address = raw_address
                    city = ""
                    
                    # Heuristic parsing: [Street, City, State, Zip, Country]
                    # Specific to "neredmet , hyderabad, , 500056, United States"
                    if len(parts) >= 2:
                        # Try to find city - usually before Zip/Country
                        candidates = []
                        for p in parts:
                            if p.lower() in ['united states', 'usa', 'us', 'india', 'uk']: continue
                            if p.replace(' ','').isdigit() or (len(p)==6 and p.isdigit()): continue # Zip code
                            candidates.append(p)
                        
                        if candidates:
                            city = candidates[-1] # Assume last non-zip/country part is City/State
                            # If multiple candidates, assume first is street
                            if len(candidates) > 1:
                                street_address = candidates[0]
                            else:
                                street_address = raw_address # Fallback to full string if unsure

                    # Build run_parameters JSON
                    run_parameters = {
                        "search": {
                            "keywords": search_keywords,
                            "location": location,
                            "distance": "50"
                        },
                        "applicant": {
                            "first_name": first_name,
                            "last_name": last_name,
                            "email": candidate.get('email', ''),
                            "phone": candidate.get('phone', ''),
                            "street_address": street_address,
                            "city": city,
                            "zip_code": candidate.get('zip_code', '')
                        },
                        "resume_url": candidate.get('resume_url', ''),
                        "resume_path": os.path.abspath(resume_path) if resume_path else "",
                        "parsed_resume": parsed_resume
                    }
                    
                    # Update candidate_marketing table
                    update_query = """
                        UPDATE candidate_marketing
                        SET run_parameters = %s,
                            last_processed_at = NOW()
                        WHERE id = %s
                    """
                    
                    json_val = json.dumps(run_parameters)
                    print(f"   DEBUG: Updating cm_id={candidate['cm_id']} with {len(json_val)} chars of JSON")
                    cursor.execute(update_query, (json_val, candidate['cm_id']))
                    connection.commit()
                    print(f"   DEBUG: Rows affected: {cursor.rowcount}")
                    
                    print(f"   ✅ Updated run_parameters")
                    success_count += 1
                    
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    error_count += 1
                    continue
                
                print("-" * 40)
            
            print("=" * 80)
            print("✅ POPULATION COMPLETE!")
            print(f"   Success: {success_count}")
            print(f"   Errors: {error_count}")
            print("=" * 80)
            
            cursor.close()
            connection.close()
            
    except Error as e:
        print(f"❌ Database Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description="Populate run_parameters for automation candidates")
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--candidate-id", type=int, help="Process logic for a SINGLE candidate ID")
    group.add_argument("--all", action="store_true", help="Process ALL active candidates (use carefully)")
    group.add_argument("--flagged-only", action="store_true", default=True, help="Process only candidates with marketing_flag=1 (default)")
    
    args = parser.parse_args()
    
    # If specific args are not set, default to flagged_only
    # Note: argparse defaults handle this, but logic is explicit here for clarity
    process_all = args.all
    candidate_id = args.candidate_id
    
    populate_run_parameters(candidate_id=candidate_id, flagged_only=True, process_all=process_all)

if __name__ == "__main__":
    main()
