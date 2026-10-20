from typing import Any

from pydantic import BaseModel, Field


class Phase1Normalized(BaseModel):
    name: str | None = None
    linkedin_url: str | None = None
    job_title: str | None = None
    current_role: str | None = None
    department: str | None = None
    location: str | None = None
    current_company: str | None = None
    company_name: str | None = None
    company_domain: str | None = None
    industry: str | None = None
    company_type: str | None = None
    employee_count: int | None = None
    employee_count_min: int | None = None
    employee_count_max: int | None = None
    hq_location: str | None = None
    company_description: str | None = None
    skills: list[str] | None = None
    professional_summary: str | None = None
    education: list[dict[str, Any]] | None = None
    open_to_work: bool | None = None
    person_follower_count: int | None = None
    company_tagline: str | None = None
    company_specialities: list[str] | None = None
    company_founded_year: int | None = None
    company_follower_count: int | None = None


class RawProviderResult(BaseModel):
    provider: str
    payload: dict[str, Any]
    raw_responses: list[dict[str, Any]] = Field(default_factory=list)
