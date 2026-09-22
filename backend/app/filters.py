from app.models import ObjectiveFilters, Profile
from app.normalize import coerce_company_type, location_tokens, normalize, skill_tokens


def skill_matches(required: str, profile_skills: list[str]) -> bool:
    required_tokens = skill_tokens(required)
    for skill in profile_skills:
        if skill_tokens(skill) & required_tokens:
            return True
        if normalize(required) in normalize(skill) or normalize(skill) in normalize(required):
            return True
    return False


def location_matches(required: str, profile_location: str) -> bool:
    return bool(location_tokens(required) & location_tokens(profile_location))


def company_matches(profile: Profile, filters: ObjectiveFilters) -> bool:
    if not filters.company_types:
        return True
    wanted = {coerce_company_type(item) or normalize(item) for item in filters.company_types}
    current = normalize(profile.current_company_type)
    past = {normalize(item.company_type) for item in profile.past_companies}
    if filters.company_history == "current":
        return current in wanted
    if filters.company_history == "past":
        return bool(past & wanted)
    return current in wanted or bool(past & wanted)


def matches(profile: Profile, filters: ObjectiveFilters) -> bool:
    if filters.locations and not any(location_matches(loc, profile.location) for loc in filters.locations):
        return False
    if filters.min_years is not None and profile.years_experience < filters.min_years:
        return False
    if filters.max_years is not None and profile.years_experience > filters.max_years:
        return False
    if filters.required_skills:
        hits = [skill_matches(skill, profile.skills) for skill in filters.required_skills]
        if filters.skill_match == "any":
            if not any(hits):
                return False
        elif not all(hits):
            return False
    if not company_matches(profile, filters):
        return False
    return True


def filter_profiles(profiles: list[Profile], filters: ObjectiveFilters) -> list[Profile]:
    return [profile for profile in profiles if matches(profile, filters)]


def pre_rank(profiles: list[Profile], filters: ObjectiveFilters, limit: int = 12) -> list[Profile]:
    def key(profile: Profile) -> tuple[int, int, int, float]:
        skill_hits = sum(1 for skill in filters.required_skills if skill_matches(skill, profile.skills))
        year_fit = 0
        if filters.min_years is not None and profile.years_experience >= filters.min_years:
            year_fit += 1
        if filters.max_years is not None and profile.years_experience <= filters.max_years:
            year_fit += 1
        type_fit = 1 if company_matches(profile, filters) else 0
        return (skill_hits, year_fit, type_fit, profile.years_experience)

    ordered = sorted(profiles, key=key, reverse=True)
    return ordered[:limit]
