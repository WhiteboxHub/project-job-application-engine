"""
parse_resume.py
---------------
Reads resume/Ghazal Sultan.pdf using pdfplumber and writes
resume/parsed_resume.json with real data extracted from the PDF.

Run:
    python scripts/parse_resume.py
"""

import os
import re
import json
import pdfplumber

# -- Paths ------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESUME_DIR = os.path.join(BASE_DIR, "resume")
PDF_PATH = os.path.join(RESUME_DIR, "candidate_resume.pdf")
OUTPUT_PATH = os.path.join(RESUME_DIR, "parsed_resume.json")


# -- Helpers ----------------------------------------------------------------
def extract_text(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def clean_name(s):
    """Handle spaced-caps name like 'G H A Z A L  S U L T A N' -> 'GHAZAL SULTAN'."""
    # If every char is separated by a space (e.g. 'G H A Z A L'), collapse them
    # Pattern: single letter, space, single letter, space...
    if re.match(r'^([A-Z] )+[A-Z]$', s.strip()):
        # Remove all spaces to get the full name string, then try to split
        # We can't know where first ends and last begins, so we use the raw PDF line
        # which has double-space between first and last name
        return s.strip()
    return s.strip()


def split_spaced_name(raw_line):
    """
    Handle PDF name formats:
    - 'G H A Z A L  S U L T A N'  (double-space between first/last)
    - 'G H A Z A L S U L T A N'   (single-space between ALL letters)
    - 'Ghazal Sultan'              (normal)
    Returns (first_name, last_name).
    """
    s = raw_line.strip()

    # Case 1: Normal name (no spaced-caps pattern)
    if not re.match(r'^([A-Za-z] )+[A-Za-z]$', s):
        parts = s.split()
        if len(parts) >= 2:
            return parts[0].title(), " ".join(parts[1:]).title()
        return s.title(), ""

    # Case 2: Double-space between first and last name
    if '  ' in s:
        parts = re.split(r'  +', s)
        first = re.sub(r' ', '', parts[0]).title()
        last = re.sub(r' ', '', parts[1]).title() if len(parts) > 1 else ""
        return first, last

    # Case 3: Single-space between ALL letters (e.g. 'G H A Z A L S U L T A N')
    # Collapse all spaces -> 'GHAZALSULTAN', then try to split into two words
    # We don't know the boundary, so we try all split points and pick the one
    # that gives two valid English-looking words (both >= 3 chars)
    collapsed_upper = re.sub(r' ', '', s)  # -> 'GHAZALSULTAN'
    best = (collapsed_upper, "")
    for i in range(3, len(collapsed_upper) - 2):
        first_part = collapsed_upper[:i].title()
        last_part = collapsed_upper[i:].title()
        # Prefer splits where both parts are at least 3 chars
        if len(first_part) >= 3 and len(last_part) >= 3:
            best = (first_part, last_part)
            break  # take the first valid split (shortest first name)
    return best[0], best[1]


def find_section(lines, *headers):
    """Return the line index of the first matching section header."""
    for i, line in enumerate(lines):
        for h in headers:
            if h.upper() in line.upper() and len(line.strip()) <= 30:
                return i
    return None


def lines_between(lines, start_idx, *end_headers):
    """Return lines from start_idx+1 until the next section header."""
    result = []
    for line in lines[start_idx + 1 :]:
        if any(h.upper() in line.upper() and len(line.strip()) <= 30 for h in end_headers):
            break
        if line.strip():
            result.append(line.strip())
    return result


# -- Section parsers --------------------------------------------------------
def parse_header(lines, raw_lines=None):
    """Extract name, title, phone, email, city/state from the top lines."""
    # Use the raw (unstripped) first line for name parsing to preserve double-spaces
    raw_name_line = (raw_lines[0] if raw_lines else lines[0]) if lines else ""

    title = lines[1].strip() if len(lines) > 1 else ""

    contact_line = ""
    for line in lines[:6]:
        if re.search(r"\+1|\d{3}[-.\s]\d{3}|@", line):
            contact_line = line
            break

    phone_match = re.search(r"\+?1?\s*[\(]?\d{3}[\)\s.-]?\s*\d{3}[-.\s]\d{4}", contact_line)
    phone = phone_match.group(0).strip() if phone_match else ""

    email_match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", contact_line)
    email = email_match.group(0).strip() if email_match else ""

    # City/State: look for pattern like "Mountain House, CA" or "SFO, CA"
    city, state = "", ""
    city_match = re.search(r"([A-Za-z\s]+),\s*([A-Z]{2})\b", contact_line)
    if city_match:
        city = city_match.group(1).strip()
        state = city_match.group(2).strip()

    # -- Name extraction --
    # Primary: extract from email if it has a dot-separated name (e.g. ghazal.sultan@...)
    first_name, last_name = "", ""
    if email:
        local = email.split("@")[0]  # e.g. 'ghazal.sultan1616'
        # Remove trailing digits
        local = re.sub(r'\d+$', '', local)
        name_parts = local.split(".")
        if len(name_parts) >= 2:
            first_name = name_parts[0].title()
            last_name = name_parts[1].title()

    # Fallback: parse the spaced-caps name line
    if not first_name:
        first_name, last_name = split_spaced_name(raw_name_line)

    return {
        "first_name": first_name,
        "last_name": last_name,
        "title": title,
        "phone": phone,
        "email": email,
        "city": city,
        "state": state,
    }


def parse_education(edu_lines):
    """Parse education section lines into structured dicts."""
    entries = []
    year_re = re.compile(r"\b(19|20)\d{2}\b")

    for line in edu_lines:
        year_match = year_re.search(line)
        # Lines like: "BACHELORS - UNIVERSITY OF SINDH, JAMSHORO, PAKISTAN"
        degree_match = re.match(
            r"(BACHELORS?|MASTERS?|PHD|DOCTORATE|ASSOCIATE|B\.?S\.?|M\.?S\.?)[^-]*[-]\s*(.+)",
            line,
            re.IGNORECASE,
        )
        if degree_match:
            degree_raw = degree_match.group(1).strip().title()
            institution_raw = degree_match.group(2).strip().title()
            entries.append(
                {
                    "institution": institution_raw,
                    "degree": degree_raw,
                    "studyType": degree_raw,
                    "area": "",
                    "endDate": year_match.group(0) if year_match else "",
                    "gpa": "",
                }
            )
        elif year_match and not entries:
            # Standalone year line before the degree line  store for next entry
            pass

    # If we got entries but no endDate, try to find a year in the section
    for entry in entries:
        if not entry["endDate"]:
            for line in edu_lines:
                ym = year_re.search(line)
                if ym:
                    entry["endDate"] = ym.group(0)
                    break

    return entries


def parse_work(work_lines):
    """
    Parse work experience lines.
    Pattern: "Company, Location  Month YYYY - Month YYYY"
    followed by "Job Title" then bullet points.
    """
    entries = []
    date_re = re.compile(
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}"
        r"\s*[-]\s*"
        r"(?:(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}|Present)",
        re.IGNORECASE,
    )
    # Also match "Oct 2023 - Present" style
    date_re2 = re.compile(
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(\d{4})\s*[-\u2013]\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{4}|Present)",
        re.IGNORECASE,
    )

    i = 0
    while i < len(work_lines):
        line = work_lines[i]
        date_match = date_re2.search(line)
        if date_match:
            # Company + location is the part before the date
            company_part = line[: date_match.start()].strip().rstrip(",").strip()
            start_raw = f"{date_match.group(1)} {date_match.group(2)}"
            end_raw = date_match.group(3).strip()

            # Next non-empty line is the job title
            title = ""
            j = i + 1
            while j < len(work_lines) and not work_lines[j].strip():
                j += 1
            if j < len(work_lines) and not date_re2.search(work_lines[j]):
                title = work_lines[j].strip()
                j += 1

            # Collect bullet points until next date line
            bullets = []
            while j < len(work_lines):
                if date_re2.search(work_lines[j]):
                    break
                bullets.append(work_lines[j].strip())
                j += 1

            summary = " ".join(b for b in bullets if b)

            entries.append(
                {
                    "name": company_part,
                    "company": company_part,
                    "position": title,
                    "title": title,
                    "startDate": start_raw,
                    "endDate": end_raw,
                    "start_date": start_raw,
                    "end_date": end_raw,
                    "summary": summary,
                    "description": summary,
                }
            )
            i = j
        else:
            i += 1

    return entries


def parse_skills(skill_lines):
    """Flatten all skill values from 'Category : skill1, skill2' lines."""
    skills = []
    for line in skill_lines:
        # Remove category prefix like "Programming : "
        if ":" in line:
            line = line.split(":", 1)[1]
        # Split by comma
        for s in line.split(","):
            s = s.strip()
            if s and len(s) < 60:  # skip overly long fragments
                skills.append(s)
    return list(dict.fromkeys(skills))  # deduplicate, preserve order


# -- Main -------------------------------------------------------------------
def parse_resume(pdf_path):
    raw = extract_text(pdf_path)
    lines = [l for l in raw.splitlines()]  # keep all lines for header parsing
    stripped = [l.strip() for l in lines]

    # -- Header --
    header = parse_header(stripped, raw_lines=lines)

    first_name = header["first_name"]
    last_name = header["last_name"]

    # -- Section boundaries --
    edu_idx = find_section(stripped, "EDUCATION")
    work_idx = find_section(stripped, "WORK EXPERIENCE", "EXPERIENCE")
    skills_idx = find_section(stripped, "SKILLS")
    summary_idx = find_section(stripped, "SUMMARY")

    section_headers = ["EDUCATION", "WORK EXPERIENCE", "EXPERIENCE", "SKILLS", "SUMMARY",
                       "CERTIFICATIONS", "PROJECTS", "LANGUAGES"]

    edu_lines = lines_between(stripped, edu_idx, *section_headers) if edu_idx is not None else []
    work_lines = lines_between(stripped, work_idx, *section_headers) if work_idx is not None else []
    skill_lines = lines_between(stripped, skills_idx, *section_headers) if skills_idx is not None else []

    # -- Parse sections --
    education = parse_education(edu_lines)
    work = parse_work(work_lines)
    skills = parse_skills(skill_lines)

    # -- Assemble output --
    result = {
        "personal_info": {
            "first_name": first_name,
            "last_name": last_name,
            "email": header["email"],
            "phone": header["phone"],
        },
        "address": {
            "street_address": "",   # Not in resume  leave blank for manual entry
            "city": header["city"],
            "state": header["state"],
            "zip_code": "",         # Not in resume  leave blank for manual entry
            "country": "United States",
        },
        "education": education,
        "work": work,
        "skills": skills,
        "professional_info": {
            "skills": skills,
            "title": header["title"],
            "summary": "",
        },
    }

    # Capture summary if present
    if summary_idx is not None:
        summary_lines = lines_between(stripped, summary_idx, *section_headers)
        result["professional_info"]["summary"] = " ".join(summary_lines)

    return result


if __name__ == "__main__":
    if not os.path.exists(PDF_PATH):
        print(f"ERROR: PDF not found at {PDF_PATH}")
        exit(1)

    print(f"Parsing: {PDF_PATH}")
    data = parse_resume(PDF_PATH)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"[OK] Written to: {OUTPUT_PATH}")
    print(f"   Name    : {data['personal_info']['first_name']} {data['personal_info']['last_name']}")
    print(f"   Email   : {data['personal_info']['email']}")
    print(f"   Phone   : {data['personal_info']['phone']}")
    print(f"   City    : {data['address']['city']}, {data['address']['state']}")
    print(f"   Jobs    : {len(data['work'])}")
    print(f"   Skills  : {len(data['skills'])}")
    print(f"   Edu     : {len(data['education'])}")
