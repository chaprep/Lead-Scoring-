import re
from urllib.parse import urlparse

from app.schemas.phase1 import Phase1Normalized


def normalize_phase1(payload: dict) -> Phase1Normalized:
    """Map provider transport data to the canonical Phase 1 schema."""
    if "person" in payload:
        return _normalize_apify(payload["person"], payload.get("company"))
    company = payload.get("company") or {}
    return Phase1Normalized(
        name=payload.get("fullName"),
        linkedin_url=payload.get("linkedinUrl"),
        job_title=payload.get("headline"),
        department=payload.get("department"),
        location=payload.get("location"),
        current_company=company.get("name"),
        company_name=company.get("name"),
        company_domain=company.get("domain"),
        industry=company.get("industry"),
        company_type=company.get("type"),
        employee_count=company.get("employeeCount"),
        employee_count_min=company.get("employeeCount"),
        employee_count_max=company.get("employeeCount"),
        hq_location=company.get("hqLocation"),
        company_description=company.get("description"),
    )


def _size_bounds(value: object) -> tuple[int | None, int | None]:
    numbers = [int(part.replace(",", "")) for part in re.findall(r"[\d,]+", str(value or ""))]
    if not numbers:
        return None, None
    if "+" in str(value):
        return numbers[0], None
    return (numbers[0], numbers[-1])


def _normalize_apify(person: dict, company: dict | None) -> Phase1Normalized:
    company = company or {}
    size_min, size_max = _size_bounds(company.get("company_size"))
    experiences = person.get("experiences") or []
    current_experience = next((item for item in experiences if not item.get("ends_at")), experiences[0] if experiences else {})
    current_title = current_experience.get("title")
    title_evidence = " ".join(filter(None, [current_title, person.get("headline")])).lower()
    department = next((label for label in ("Revenue Operations", "Sales", "Marketing", "Finance", "Engineering") if label.lower() in title_evidence), None)
    location = ", ".join(filter(None, [person.get("city"), person.get("country")])) or None
    hq = company.get("hq") or {}
    hq_location = ", ".join(filter(None, [hq.get("city"), hq.get("country")])) if isinstance(hq, dict) else hq
    domain = urlparse(company.get("website") or "").netloc or None
    return Phase1Normalized(name=person.get("full_name"), linkedin_url=person.get("url"), job_title=person.get("headline"), current_role=current_title, department=department, location=location, current_company=person.get("company_name"), company_name=company.get("name"), company_domain=domain, industry=company.get("industry"), employee_count=size_min if size_min == size_max else None, employee_count_min=size_min, employee_count_max=size_max, hq_location=hq_location, company_description=company.get("description"), skills=person.get("skills"), professional_summary=person.get("summary"), education=person.get("education"), open_to_work=person.get("open_to_work"), person_follower_count=person.get("follower_count"), company_tagline=company.get("tagline"), company_specialities=company.get("specialities"), company_founded_year=company.get("founded_year"), company_follower_count=company.get("follower_count"))
