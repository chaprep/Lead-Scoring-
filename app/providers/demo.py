"""Deterministic fictional providers for trying the workflow without external services.

These scenarios demonstrate control flow, not model quality or actual prospect research.
"""
from urllib.parse import urlparse

from app.core.enums import QualificationDecision
from app.providers.qualification.base import QualificationOutcome
from app.schemas.phase1 import RawProviderResult

SCENARIOS = [
    {"slug": "demo-alex-morgan", "name": "Alex Morgan", "company": "Northstar Cloud", "domain": "northstar.example", "priority": "P1", "decision": "PASS"},
    {"slug": "demo-sam-rivera", "name": "Sam Rivera", "company": "Relay Systems", "domain": "relay.example", "priority": "P2", "decision": "HUMAN_REVIEW"},
    {"slug": "demo-jordan-lee", "name": "Jordan Lee", "company": "Arc Software", "domain": "arc.example", "priority": "P3", "decision": "PASS"},
    {"slug": "demo-nina-patel", "name": "Nina Patel", "company": "Fieldwork AI", "domain": "fieldwork.example", "priority": "P1", "decision": "PASS"},
    {"slug": "demo-lena-chen", "name": "Lena Chen", "company": "Scale Advisory", "domain": "scale.example", "priority": "P3", "decision": "REJECTED"},
    {"slug": "demo-omar-davis", "name": "Omar Davis", "company": "Vector Cloud", "domain": "vector.example", "priority": "P2", "decision": "PASS"},
]


def sample_prospects() -> list[dict[str, str]]:
    return [{"name": s["name"], "linkedin_url": f'https://www.linkedin.com/in/{s["slug"]}'} for s in SCENARIOS]


def scenario_for_url(url: str) -> dict[str, str]:
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    return next((s for s in SCENARIOS if s["slug"] == slug), SCENARIOS[0])


def scenario_for_domain(domain: str | None) -> dict[str, str]:
    return next((s for s in SCENARIOS if s["domain"] == domain), SCENARIOS[0])


class DemoProfileProvider:
    provider_name = "demo_profile"

    async def enrich(self, name: str, linkedin_url: str) -> RawProviderResult:
        s = scenario_for_url(linkedin_url)
        role = "Revenue Operations Lead" if s["decision"] == "HUMAN_REVIEW" else "VP, Revenue Operations"
        if s["decision"] == "REJECTED":
            role = "Operations Consultant"
        return RawProviderResult(provider=self.provider_name, payload={
            "demo": True,
            "notice": "Fictional fixture. No profile was fetched; outcomes are scripted.",
            "fullName": name, "linkedinUrl": linkedin_url, "headline": role,
            "department": "Revenue Operations", "location": "United States",
            "company": {"name": s["company"], "domain": s["domain"], "industry": "B2B software", "type": "SaaS", "employeeCount": 640, "hqLocation": "United States", "description": "Fictional software company used for the local demo."},
        })


class DemoQualificationProvider:
    provider_name = "demo_qualification"

    async def decide(self, icp, data) -> QualificationOutcome:
        s = scenario_for_domain(data.company_domain)
        decision = QualificationDecision(s["decision"])
        reason = {
            "PASS": "Demo scenario: the fictional role and company pass qualification.",
            "HUMAN_REVIEW": "Demo scenario: the title says Lead; seniority is unclear. Approve or reject this prospect.",
            "REJECTED": "Demo scenario: consultancy work falls within the example exclusions.",
        }[s["decision"]]
        return QualificationOutcome(
            decision=decision, person_fit="UNCERTAIN" if decision is QualificationDecision.HUMAN_REVIEW else "MATCH",
            company_fit="MISMATCH" if decision is QualificationDecision.REJECTED else "MATCH",
            exclusion_flags=["Example consultancy exclusion"] if decision is QualificationDecision.REJECTED else [],
            reason=reason, confidence="medium" if decision is QualificationDecision.HUMAN_REVIEW else "high",
            assessments={"demo": True, "notice": "Predetermined scenario; custom ICP criteria are not evaluated in demo mode."},
            overall_fit_band="demo", confidence_band="demo", model_identifier="fictional-demo-v1",
            provider_identifier=self.provider_name, usage_metadata={},
        )


class DemoCompanyProvider:
    provider_name = "demo_company"

    async def enrich(self, domain: str | None) -> RawProviderResult:
        s = scenario_for_domain(domain)
        return RawProviderResult(provider=self.provider_name, payload={
            "demo": True, "domain": s["domain"], "name": s["company"],
            "demo_priority": s["priority"], "funding": None,
            "hiring": "Example revenue-team roles open" if s["priority"] == "P1" else None,
            "technology": "Example sales technology" if s["priority"] == "P1" else None,
            "notice": "Fictional company signals, not retrieved from a provider.",
        })


class DemoPriorityProvider:
    provider_name = "demo_priority"
    model = "fictional-demo-v1"

    async def decide(self, context: dict) -> tuple[dict, dict]:
        priority = context.get("company_enrich_data", {}).get("demo_priority", "P2")
        result = {
            "priority": priority, "confidence": "medium",
            "positive_signals": ["Fictional ICP fit", "Fictional hiring signal"] if priority == "P1" else ["Fictional ICP fit"],
            "negative_or_unknown_signals": ["Funding information unavailable in this example"],
            "reason": f"Demo scenario: predetermined {priority} priority for exploring the workflow.",
            "summary": f"Fictional {priority} result. This is not a live lead assessment.",
            "criteria_assessments": {field: "unknown" for field in ["company_icp_fit", "company_size", "industry", "company_type", "geography", "funding", "growth_or_hiring", "technology"]},
        }
        return result, {"request": {"demo": True}, "response": {"demo": True, "usage": {}}}


def contact_payload(name: str) -> dict:
    return {"items": [{"status": "success", "candidate": {
        "uid": "fictional-demo", "fullName": name,
        "contacts": [{"type": "email", "value": "demo.prospect@example.com"}, {"type": "phone", "value": "+1 415 555 0142"}],
    }}], "demo": True}
