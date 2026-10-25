"""
Resume Analyzer Service for CareerSync.

Performs deterministic rule-based NLP extraction on resume text:
- Extracts contact details (name, email, phone)
- Matches skills against the 42 seeded catalog skills with exact boundary patterns
- Extracts academic history (institution, degree, field of study, years, GPA)
- Extracts projects (title, description, technologies used)
- Extracts practical experience (organization, role title, duration, description)
"""
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import (
    Resume,
    ResumeEducation,
    ResumeExperience,
    ResumeProject,
    ResumeSkill,
    Skill,
)

logger = logging.getLogger("careersync.services.resume_analyzer")

# ---------------------------------------------------------------------------
# 1. Precise Regex Patterns for the 42 Seeded Catalog Skills
# Punctuation-safe patterns to prevent false positives (e.g. C++, Java, Node.js)
# ---------------------------------------------------------------------------
SKILL_PATTERNS: Dict[str, str] = {
    # Programming Languages
    "Python": r"\bPython\b",
    "JavaScript": r"\b(?:JavaScript|JS)\b",
    "TypeScript": r"\b(?:TypeScript|TS)\b",
    "Java": r"\bJava\b(?![#+a-zA-Z])",
    "C++": r"(?<![a-zA-Z0-9+])C\+\+(?![+])",
    "SQL": r"\bSQL\b",
    "HTML5": r"\bHTML5?\b",
    "CSS3": r"\bCSS3?\b",
    # Frameworks & Libraries
    "FastAPI": r"\bFastAPI\b",
    "Flask": r"\bFlask\b",
    "Django": r"\bDjango\b",
    "React": r"\bReact(?:\.?js)?\b",
    "Node.js": r"\bNode[\s.-]?js\b",
    "Express.js": r"\bExpress[\s.-]?(?:js)?\b",
    "Pandas": r"\bPandas\b",
    "NumPy": r"\bNumPy\b",
    "Tailwind CSS": r"\bTailwind(?:\s*CSS)?\b",
    "Spring Boot": r"\b(?:Spring\s+Boot|Spring\s+Framework)\b",
    "React Native": r"\b(?:React\s+Native|Flutter)\b",
    # Databases
    "MySQL": r"\bMySQL\b",
    "PostgreSQL": r"\b(?:PostgreSQL|Postgres)\b",
    "SQLite": r"\bSQLite3?\b",
    "MongoDB": r"\b(?:MongoDB|Mongo)\b",
    "Redis": r"\bRedis\b",
    # Tools & Platforms
    "Git": r"\bGit\b(?!Hub|Lab|[a-zA-Z])",
    "GitHub": r"\bGitHub\b",
    "Docker": r"\bDocker\b",
    "Postman": r"\bPostman\b",
    "Linux / Bash": r"\b(?:Linux|Bash|Shell\s*Script(?:ing)?)\b",
    "VS Code": r"\b(?:VS\s*Code|Visual\s+Studio\s+Code)\b",
    "Nginx": r"\bNginx\b",
    "Power BI": r"\bPower\s*BI\b",
    "Tableau": r"\bTableau\b",
    "Selenium": r"\bSelenium\b",
    "Figma": r"\b(?:Figma|Adobe\s+XD|Sketch)\b",
    # Cloud & DevOps
    "Amazon Web Services (AWS)": r"\b(?:AWS|Amazon\s+Web\s+Services)\b",
    "Microsoft Azure": r"\b(?:Microsoft\s+Azure|Azure)\b",
    "Google Cloud Platform (GCP)": r"\b(?:Google\s+Cloud(?:\s+Platform)?|GCP)\b",
    "CI/CD Pipelines": r"\b(?:CI[/-]?CD(?:\s+Pipelines?)?)\b",
    "Kubernetes": r"\b(?:Kubernetes|K8s)\b",
    # Core Concepts
    "RESTful APIs": r"\b(?:REST(?:ful)?(?:\s+APIs?)?)\b",
    "Data Structures & Algorithms": r"\b(?:Data\s+Structures(?:\s*&\s*|\s+and\s+)Algorithms|DSA)\b",
    "Object-Oriented Programming (OOP)": r"\b(?:Object[- ]Oriented\s+Programming|OOP)\b",
    "Database Normalization": r"\bDatabase\s+Normalization\b",
    "Unit Testing": r"\b(?:Unit\s+Test(?:ing|s)?|pytest|unittest|JUnit)\b",
    "Web Security Basics": r"\b(?:Web\s+Security(?:\s+Basics)?|OWASP)\b",
    "Network Security": r"\b(?:Network\s+Security|Wireshark|Firewalls?|Penetration\s+Testing)\b",
    "Machine Learning": r"\b(?:Machine\s+Learning|Scikit[- ]learn|TensorFlow|PyTorch|Deep\s+Learning)\b",
    "Agile / Scrum": r"\b(?:Agile|Scrum|Jira|Sprint\s+Planning)\b",
    # Soft Skills
    "Technical Communication": r"\bTechnical\s+Communication\b",
    "Problem Solving": r"\bProblem\s+Solving\b",
    "Team Collaboration": r"\b(?:Team\s+Collaboration|Teamwork|Cross-functional\s+collaboration)\b",
}

# Compiled regex cache for skill patterns
COMPILED_SKILL_PATTERNS: Dict[str, re.Pattern] = {
    name: re.compile(pat, re.IGNORECASE) for name, pat in SKILL_PATTERNS.items()
}

# ---------------------------------------------------------------------------
# 2. Section Header Regexes
# ---------------------------------------------------------------------------
SECTION_HEADER_PATTERNS: List[Tuple[str, re.Pattern]] = [
    (
        "EDUCATION",
        re.compile(
            r"^\s*(?:#+\s*)?(?:EDUCATION|ACADEMIC\s+BACKGROUND|ACADEMIC\s+QUALIFICATIONS|QUALIFICATIONS)\s*:?$",
            re.IGNORECASE,
        ),
    ),
    (
        "SKILLS",
        re.compile(
            r"^\s*(?:#+\s*)?(?:TECHNICAL\s+SKILLS|SKILLS(?:\s*(&|and)\s*(?:TECHNOLOGIES|TOOLS))?|CORE\s+COMPETENCIES|AREAS\s+OF\s+EXPERTISE)\s*:?$",
            re.IGNORECASE,
        ),
    ),
    (
        "EXPERIENCE",
        re.compile(
            r"^\s*(?:#+\s*)?(?:WORK\s+EXPERIENCE|PROFESSIONAL\s+EXPERIENCE|EXPERIENCE|EMPLOYMENT\s+HISTORY|INTERNSHIPS)\s*:?$",
            re.IGNORECASE,
        ),
    ),
    (
        "PROJECTS",
        re.compile(
            r"^\s*(?:#+\s*)?(?:(?:TECHNICAL|PERSONAL|ACADEMIC|KEY)?\s*PROJECTS)\s*:?$",
            re.IGNORECASE,
        ),
    ),
]


def segment_sections(raw_text: str) -> Dict[str, str]:
    """
    Split resume raw text into distinct sections based on recognized headings.
    Returns a dict mapping section names to text content.
    Always includes 'HEADER', 'SKILLS', 'EXPERIENCE', 'PROJECTS', 'EDUCATION'.
    """
    lines = raw_text.splitlines()
    detected_headers: List[Tuple[int, str]] = []

    for idx, line in enumerate(lines):
        clean_line = line.strip().strip("*#_~").strip()
        if not clean_line or len(clean_line) > 50:
            continue
        for sec_name, pat in SECTION_HEADER_PATTERNS:
            if pat.match(clean_line):
                detected_headers.append((idx, sec_name))
                break

    sections: Dict[str, List[str]] = {
        "HEADER": [],
        "SKILLS": [],
        "EXPERIENCE": [],
        "PROJECTS": [],
        "EDUCATION": [],
        "OTHER": [],
    }

    if not detected_headers:
        # If no explicit headings, place all text in 'HEADER'
        sections["HEADER"] = lines
    else:
        # Everything before the first header is the HEADER section
        first_idx = detected_headers[0][0]
        sections["HEADER"] = lines[:first_idx]

        for i, (start_idx, sec_name) in enumerate(detected_headers):
            end_idx = (
                detected_headers[i + 1][0]
                if i + 1 < len(detected_headers)
                else len(lines)
            )
            # Exclude the header line itself
            sec_lines = lines[start_idx + 1 : end_idx]
            sections[sec_name].extend(sec_lines)

    return {k: "\n".join(v).strip() for k, v in sections.items()}


# ---------------------------------------------------------------------------
# 3. Contact Details Extraction
# ---------------------------------------------------------------------------
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", re.IGNORECASE
)
PHONE_REGEX = re.compile(
    r"(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}|\+?\d{1,3}[\s.-]?[6-9]\d{9}",
    re.IGNORECASE,
)


def extract_contact_info(
    header_text: str, full_text: str
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extract candidate name, email, and phone number without hallucinating.
    Returns (name, email, phone).
    """
    # 1. Email (search header first, fallback to full text)
    email_match = EMAIL_REGEX.search(header_text) or EMAIL_REGEX.search(full_text)
    email = email_match.group(0).strip() if email_match else None

    # 2. Phone
    phone_match = PHONE_REGEX.search(header_text) or PHONE_REGEX.search(full_text)
    phone = phone_match.group(0).strip() if phone_match else None

    # 3. Candidate Name from top lines of Header
    name: Optional[str] = None
    for line in header_text.splitlines():
        clean = line.strip().strip("*#_~").strip()
        if not clean:
            continue
        # Skip lines that look like email, phone, URLs, or labels
        if EMAIL_REGEX.search(clean) or PHONE_REGEX.search(clean):
            continue
        if re.search(
            r"^(?:email|phone|address|linkedin|github|portfolio|curriculum|resume|cv)\b",
            clean,
            re.IGNORECASE,
        ):
            continue
        if any(c in clean for c in ["@", "http:", "https:", "www."]):
            continue
        # Name should be 1 to 4 words of reasonable length
        words = clean.split()
        if 1 <= len(words) <= 4 and len(clean) <= 60:
            # Check characters are mostly letters/spaces
            if re.match(r"^[A-Za-z\s.'-]+$", clean):
                name = clean
                break

    return name, email, phone


# ---------------------------------------------------------------------------
# 4. Catalog Skills Matching & Source Tracking
# ---------------------------------------------------------------------------
def extract_skills_data(
    sections: Dict[str, str],
    full_text: str,
    catalog_skills: List[Skill],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Match skills against catalog skills and determine extraction source.
    Returns (matched_skills, unmatched_skills).
    """
    matched: List[Dict[str, Any]] = []
    matched_ids: Set[int] = set()

    # Pre-build lookup map: Skill.name -> Skill
    skill_map = {s.name: s for s in catalog_skills}

    # Check each catalog skill
    for skill_name, pattern in COMPILED_SKILL_PATTERNS.items():
        skill_obj = skill_map.get(skill_name)
        if not skill_obj:
            continue

        # Check in order of priority:
        # SKILLS_SECTION > PROJECTS > EXPERIENCE > EDUCATION > OTHER
        extraction_source: Optional[str] = None

        if sections["SKILLS"] and pattern.search(sections["SKILLS"]):
            extraction_source = "SKILLS_SECTION"
        elif sections["PROJECTS"] and pattern.search(sections["PROJECTS"]):
            extraction_source = "PROJECTS"
        elif sections["EXPERIENCE"] and pattern.search(sections["EXPERIENCE"]):
            extraction_source = "EXPERIENCE"
        elif sections["EDUCATION"] and pattern.search(sections["EDUCATION"]):
            extraction_source = "EDUCATION"
        elif pattern.search(full_text):
            extraction_source = "SKILLS_SECTION"

        if extraction_source and skill_obj.id not in matched_ids:
            matched_ids.add(skill_obj.id)
            matched.append(
                {
                    "skill_id": skill_obj.id,
                    "skill_name": skill_obj.name,
                    "category": skill_obj.category,
                    "extraction_source": extraction_source,
                }
            )

    # Detect potential unmatched skills in skills section for informational response
    unmatched: List[str] = []
    if sections["SKILLS"]:
        # Tokens separated by commas, bullets, or slashes
        tokens = re.split(r"[,•|;\n]", sections["SKILLS"])
        for token in tokens:
            t = token.strip().strip("-*").strip()
            if not t or len(t) < 2 or len(t) > 30:
                continue
            if re.search(r"^(?:languages|frameworks|tools|databases|skills)\b", t, re.I):
                continue
            # If not already matched
            matched_names = {m["skill_name"].lower() for m in matched}
            if t.lower() not in matched_names and not any(
                pat.search(t) for pat in COMPILED_SKILL_PATTERNS.values()
            ):
                if re.match(r"^[A-Za-z0-9#+.\s-]+$", t) and t not in unmatched:
                    unmatched.append(t)

    return matched, unmatched[:10]  # Limit unmatched to top 10 for clean payload


# ---------------------------------------------------------------------------
# 5. Education Details Extraction
# ---------------------------------------------------------------------------
DEGREE_REGEX = re.compile(
    r"\b(?:B\.?Tech|B\.?E\.?|B\.?S\.?(?:c)?|M\.?Tech|M\.?E\.?|M\.?S\.?(?:c)?|B\.?C\.?A\.?|M\.?C\.?A\.?|Ph\.?D\.?|Bachelor\s+(?:of\s+[A-Za-z\s]+)?|Master\s+(?:of\s+[A-Za-z\s]+)?|Associate\s+(?:of\s+[A-Za-z\s]+)?|Diploma|High\s+School)\b",
    re.IGNORECASE,
)
YEARS_REGEX = re.compile(
    r"\b(20\d{2}|19\d{2})\s*(?:-|–|to)\s*(20\d{2}|19\d{2}|present|current)\b",
    re.IGNORECASE,
)
CGPA_REGEX = re.compile(
    r"\b(?:CGPA|GPA|Score|Percentage)?\s*:?\s*(\d{1,2}(?:\.\d{1,2})?\s*(?:/\s*(?:10|4\.0|4|100)|%)|\b[3-9]\.\d{1,2}\b)",
    re.IGNORECASE,
)
FIELD_REGEX = re.compile(
    r"\bin\s+([A-Za-z\s]+?)(?=\s*[|,–-]|\s*\d{4}|$)", re.IGNORECASE
)
INST_KEYWORDS = ["university", "college", "institute", "academy", "school"]


def extract_education_entries(edu_text: str) -> List[Dict[str, Any]]:
    """
    Extract structured education entries from the Education section.
    If no education section is present or no valid entries found, returns [].
    """
    if not edu_text.strip():
        return []

    entries: List[Dict[str, Any]] = []
    # Split by blank lines or paragraphs
    blocks = [b.strip() for b in re.split(r"\n\s*\n", edu_text) if b.strip()]

    for block in blocks:
        institution: Optional[str] = None
        degree: Optional[str] = None
        field_of_study: Optional[str] = None
        start_year: Optional[int] = None
        end_year: Optional[int] = None
        grade_or_cgpa: Optional[str] = None

        lines = [l.strip() for l in block.splitlines() if l.strip()]
        for line in lines:
            # Institution
            if not institution:
                if any(k in line.lower() for k in INST_KEYWORDS):
                    institution = line.split("|")[0].strip().rstrip(",-")
            # Degree
            if not degree:
                deg_match = DEGREE_REGEX.search(line)
                if deg_match:
                    degree = deg_match.group(0).strip().rstrip(",-")
            # Field of study
            if not field_of_study:
                field_match = FIELD_REGEX.search(line)
                if field_match:
                    clean_field = field_match.group(1).strip().rstrip(",-")
                    if clean_field and len(clean_field) <= 150:
                        field_of_study = clean_field
            # Years
            if not start_year:
                yr_match = YEARS_REGEX.search(line)
                if yr_match:
                    try:
                        start_year = int(yr_match.group(1))
                        end_val = yr_match.group(2).lower()
                        if end_val.isdigit():
                            end_year = int(end_val)
                    except ValueError:
                        pass
            # Grade / CGPA
            if not grade_or_cgpa:
                gpa_match = CGPA_REGEX.search(line)
                if gpa_match:
                    grade_or_cgpa = gpa_match.group(1).strip()

        # Only create entry if at least institution or degree is identified
        if institution or degree:
            entries.append(
                {
                    "institution": institution[:255] if institution else None,
                    "degree": degree[:150] if degree else None,
                    "field_of_study": field_of_study[:150] if field_of_study else None,
                    "start_year": start_year,
                    "end_year": end_year,
                    "grade_or_cgpa": grade_or_cgpa[:50] if grade_or_cgpa else None,
                }
            )

    return entries


# ---------------------------------------------------------------------------
# 6. Projects Extraction
# ---------------------------------------------------------------------------
def extract_project_entries(
    proj_text: str, catalog_skills: List[Skill]
) -> List[Dict[str, Any]]:
    """
    Extract structured project entries from the Projects section.
    Returns [] if no projects are found.
    """
    if not proj_text.strip():
        return []

    entries: List[Dict[str, Any]] = []
    # Split projects by blank lines or headers
    blocks = [b.strip() for b in re.split(r"\n\s*\n", proj_text) if b.strip()]

    for idx, block in enumerate(blocks, start=1):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue

        # First line is title
        raw_title = lines[0].strip().lstrip("*#-_•").strip()
        # Remove pipe delimiters (e.g. "Project Name | React, Node.js")
        title_parts = raw_title.split("|")
        title = title_parts[0].strip() or f"Project {idx}"

        # Detect technologies mentioned in this project block
        techs_found: List[str] = []
        for s in catalog_skills:
            pat = COMPILED_SKILL_PATTERNS.get(s.name)
            if pat and pat.search(block):
                techs_found.append(s.name)

        tech_str: Optional[str] = (
            ", ".join(sorted(set(techs_found))) if techs_found else None
        )
        if tech_str and len(tech_str) > 500:
            tech_str = tech_str[:500]

        # Remaining lines form description
        desc_lines = [l for l in lines[1:] if not l.lower().startswith("technologies:")]
        desc = "\n".join(desc_lines).strip() if desc_lines else None

        entries.append(
            {
                "title": title[:255],
                "description": desc,
                "technologies_used": tech_str,
            }
        )

    return entries


# ---------------------------------------------------------------------------
# 7. Work Experience Extraction
# ---------------------------------------------------------------------------
ROLE_REGEX = re.compile(
    r"\b(?:(?:Senior|Junior|Lead|Associate|Staff|Principal)\s+)?(?:Software|Backend|Frontend|Full[\s-]?Stack|DevOps|Data|Cloud|Web|System|Mobile)?\s*(?:Engineer|Developer|Specialist|Analyst|Consultant|Architect|Manager)(?:\s+Intern)?\b|\bIntern\b",
    re.IGNORECASE,
)
DURATION_REGEX = re.compile(
    r"\b(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4})\s*(?:-|–|to)\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4}|present|current)\b",
    re.IGNORECASE,
)


def extract_experience_entries(exp_text: str) -> List[Dict[str, Any]]:
    """
    Extract work experience / internship entries.
    Returns [] if no experience section or entries found.
    """
    if not exp_text.strip():
        return []

    entries: List[Dict[str, Any]] = []
    blocks = [b.strip() for b in re.split(r"\n\s*\n", exp_text) if b.strip()]

    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue

        role_title: Optional[str] = None
        organization: Optional[str] = None
        duration: Optional[str] = None
        bullets: List[str] = []

        for line in lines:
            # Check for role
            if not role_title:
                role_match = ROLE_REGEX.search(line)
                if role_match:
                    role_title = role_match.group(0).strip()
                    continue

            # Check for duration
            if not duration:
                dur_match = DURATION_REGEX.search(line)
                if dur_match:
                    duration = dur_match.group(0).strip()
                    # Company may be before pipe
                    if "|" in line:
                        parts = line.split("|")
                        if not organization and parts[0].strip():
                            organization = parts[0].strip()
                    continue

            # Check for organization
            if not organization and not line.startswith(("-", "*", "•")):
                organization = line.split("|")[0].strip().rstrip(",-")
                continue

            bullets.append(line)

        # Only add if role or organization is detected
        if role_title or organization:
            entries.append(
                {
                    "organization": organization[:255] if organization else None,
                    "role_title": role_title[:150] if role_title else None,
                    "duration": duration[:100] if duration else None,
                    "description": "\n".join(bullets).strip() if bullets else None,
                }
            )

    return entries


# ---------------------------------------------------------------------------
# 8. Master Orchestrator (Transactional Execution)
# ---------------------------------------------------------------------------
def analyze_resume_transactional(
    resume_id: int,
    db: Session,
) -> Dict[str, Any]:
    """
    Perform transactional analysis of a resume:
    1. Fetches resume and verifies parsing_status == 'PARSED' and raw_text is present.
    2. Runs rule-based NLP extraction for contacts, skills, education, projects, experience.
    3. Transactionally clears previous child records for this resume_id only.
    4. Inserts newly parsed child records and updates resume contact info.
    5. Returns structured analysis dict.
    If an error occurs, rolls back cleanly preserving prior state.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise ValueError(f"Resume with ID {resume_id} not found.")

    if resume.parsing_status != "PARSED" or not resume.raw_text:
        raise ValueError(
            f"Resume {resume_id} has parsing status '{resume.parsing_status}' and cannot be analyzed."
        )

    raw_text = resume.raw_text
    catalog_skills = db.query(Skill).all()

    # Step 1: Segment text into sections
    sections = segment_sections(raw_text)

    # Step 2: Extract details
    cand_name, cand_email, cand_phone = extract_contact_info(
        sections["HEADER"], raw_text
    )
    matched_skills, unmatched_skills = extract_skills_data(
        sections, raw_text, catalog_skills
    )
    education_entries = extract_education_entries(sections["EDUCATION"])
    project_entries = extract_project_entries(sections["PROJECTS"], catalog_skills)
    experience_entries = extract_experience_entries(sections["EXPERIENCE"])

    # Step 3: Transactional database update
    try:
        # Atomic delete of existing child records for this resume ONLY
        db.query(ResumeSkill).filter(ResumeSkill.resume_id == resume_id).delete(
            synchronize_session=False
        )
        db.query(ResumeEducation).filter(
            ResumeEducation.resume_id == resume_id
        ).delete(synchronize_session=False)
        db.query(ResumeProject).filter(ResumeProject.resume_id == resume_id).delete(
            synchronize_session=False
        )
        db.query(ResumeExperience).filter(
            ResumeExperience.resume_id == resume_id
        ).delete(synchronize_session=False)

        # Update candidate info and analysis completion timestamp on resumes table
        resume.updated_at = func.now()
        resume.analysis_completed_at = func.now()
        if cand_name:
            resume.candidate_name = cand_name[:150]
        if cand_email:
            resume.candidate_email = cand_email[:255]
        if cand_phone:
            resume.candidate_phone = cand_phone[:50]

        # Insert new skills
        for s in matched_skills:
            rs = ResumeSkill(
                resume_id=resume_id,
                skill_id=s["skill_id"],
                extraction_source=s["extraction_source"],
            )
            db.add(rs)

        # Insert new education
        for edu in education_entries:
            re_edu = ResumeEducation(
                resume_id=resume_id,
                institution=edu["institution"],
                degree=edu["degree"],
                field_of_study=edu["field_of_study"],
                start_year=edu["start_year"],
                end_year=edu["end_year"],
                grade_or_cgpa=edu["grade_or_cgpa"],
            )
            db.add(re_edu)

        # Insert new projects
        for proj in project_entries:
            rp = ResumeProject(
                resume_id=resume_id,
                title=proj["title"],
                description=proj["description"],
                technologies_used=proj["technologies_used"],
            )
            db.add(rp)

        # Insert new experience
        for exp in experience_entries:
            rexp = ResumeExperience(
                resume_id=resume_id,
                organization=exp["organization"],
                role_title=exp["role_title"],
                duration=exp["duration"],
                description=exp["description"],
            )
            db.add(rexp)

        db.commit()
        db.refresh(resume)

        logger.info(
            "Resume %s analyzed successfully: %s skills, %s edu, %s projects, %s exp",
            resume_id,
            len(matched_skills),
            len(education_entries),
            len(project_entries),
            len(experience_entries),
        )

        return {
            "resume_id": resume.id,
            "candidate": {
                "candidate_name": resume.candidate_name,
                "candidate_email": resume.candidate_email,
                "candidate_phone": resume.candidate_phone,
            },
            "skills": matched_skills,
            "education": education_entries,
            "projects": project_entries,
            "experience": experience_entries,
            "unmatched_skills": unmatched_skills,
            "analysis_completed_at": resume.analysis_completed_at,
            "message": f"Resume analyzed successfully: {len(matched_skills)} catalog skills matched.",
        }

    except Exception as e:
        db.rollback()
        logger.error("Analysis failed for resume %s; rolled back: %s", resume_id, e)
        raise e
