from app.models import Citation, Profile
from app.normalize import contains_text, normalize


FIELD_LABELS = {
    "skills": "Skills",
    "years_experience": "Experience",
    "location": "Location",
    "current_company": "Company",
    "current_company_type": "Company type",
    "current_title": "Title",
    "education": "Education",
    "summary": "Summary",
    "past_companies": "Past companies",
    "name": "Name",
}


def field_text(profile: Profile, field: str) -> str:
    if field == "skills":
        return ", ".join(profile.skills)
    if field == "past_companies":
        parts = []
        for item in profile.past_companies:
            parts.append(f"{item.company} ({item.company_type}, {item.title}, {item.years} years)")
        return "; ".join(parts)
    if field == "years_experience":
        return str(profile.years_experience).removesuffix(".0")
    value = getattr(profile, field, "")
    return str(value)


def citation_is_valid(profile: Profile, citation: Citation) -> bool:
    if citation.field not in FIELD_LABELS:
        return False
    return contains_text(field_text(profile, citation.field), citation.quote)


def validate_citations(profile: Profile, citations: list[Citation]) -> list[Citation]:
    kept: list[Citation] = []
    seen: set[tuple[str, str]] = set()
    for citation in citations:
        key = (citation.field, normalize(citation.quote))
        if key in seen or not citation_is_valid(profile, citation):
            continue
        seen.add(key)
        kept.append(citation)
    return kept


def infer_citations(profile: Profile, reason: str) -> list[Citation]:
    found: list[Citation] = []
    seen: set[str] = set()

    def add(field: str, quote: str) -> None:
        marker = normalize(quote)
        if not marker or marker in seen:
            return
        if contains_text(reason, quote):
            seen.add(marker)
            found.append(Citation(field=field, quote=quote))

    for skill in profile.skills:
        add("skills", skill)
    add("current_title", profile.current_title)
    add("current_company", profile.current_company)
    add("location", profile.location)
    add("current_company_type", profile.current_company_type)
    add("education", profile.education)
    years = str(profile.years_experience).removesuffix(".0")
    if years and years in reason:
        add("years_experience", years)
    for past in profile.past_companies:
        add("past_companies", past.company)
    return found
