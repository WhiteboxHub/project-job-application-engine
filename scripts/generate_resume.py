import json
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def generate_resume_pdf():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, 'resume', 'resume.json')
    pdf_path = os.path.join(base_dir, 'resume', 'candidate_resume.pdf')
    
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    with open(json_path, 'r') as f:
        data = json.load(f)

    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter
    y = height - 50
    
    # Header
    basics = data.get('basics', {})
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, basics.get('name', 'Name'))
    y -= 20
    c.setFont("Helvetica", 12)
    c.drawString(50, y, f"{basics.get('label', '')} | {basics.get('email', '')} | {basics.get('phone', '')}")
    y -= 15
    c.drawString(50, y, f"{basics.get('location', {}).get('city', '')}, {basics.get('location', {}).get('region', '')}")
    y -= 30
    
    # Summary
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Summary")
    y -= 20
    c.setFont("Helvetica", 10)
    summary = basics.get('summary', '')
    # Simple formatting for wrapping not implemented for brevity, assuming short summary
    c.drawString(50, y, summary)
    y -= 30
    
    # Work Experience
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Experience")
    y -= 20
    
    for job in data.get('work', []):
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, f"{job.get('position', '')} at {job.get('name', '')}")
        c.setFont("Helvetica", 10)
        c.drawRightString(width - 50, y, f"{job.get('startDate', '')} - {job.get('endDate', 'Present')}")
        y -= 15
        c.drawString(60, y, job.get('summary', ''))
        y -= 25
        
    # Education
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Education")
    y -= 20
    for edu in data.get('education', []):
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, edu.get('institution', ''))
        c.setFont("Helvetica", 10)
        c.drawRightString(width - 50, y, f"{edu.get('startDate', '')} - {edu.get('endDate', '')}")
        y -= 15
        c.drawString(60, y, f"{edu.get('studyType', '')} in {edu.get('area', '')}")
        y -= 25

    # Skills
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Skills")
    y -= 20
    c.setFont("Helvetica", 10)
    for skill in data.get('skills', []):
        keywords = ", ".join(skill.get('keywords', []))
        c.drawString(50, y, f"{skill.get('name', '')}: {keywords}")
        y -= 15

    c.save()
    print(f"Resume PDF generated at: {pdf_path}")

if __name__ == "__main__":
    generate_resume_pdf()
