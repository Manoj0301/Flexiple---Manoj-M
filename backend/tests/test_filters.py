from app.filters import filter_profiles, matches
from app.models import ObjectiveFilters, PastCompany, Profile


def profile(**overrides) -> Profile:
    data = {
        "id": "p01",
        "name": "Ananya Rao",
        "current_title": "Senior Backend Engineer",
        "years_experience": 6,
        "location": "Bangalore",
        "current_company": "NimbusPay",
        "current_company_type": "startup",
        "skills": ["Node.js", "PostgreSQL", "AWS RDS"],
        "past_companies": [
            PastCompany(company="Zeta", company_type="scaleup", title="Backend Engineer", years=2)
        ],
        "education": "B.E. Computer Science",
        "summary": "Backend engineer.",
    }
    data.update(overrides)
    return Profile.model_validate(data)


def filters(**overrides) -> ObjectiveFilters:
    return ObjectiveFilters.model_validate(overrides)


def test_rds_alias_matches_aws_rds():
    person = profile()
    assert matches(person, filters(required_skills=["RDS"], skill_match="all"))


def test_all_skills_required():
    person = profile()
    assert not matches(person, filters(required_skills=["AWS RDS", "Kafka"], skill_match="all"))
    assert matches(person, filters(required_skills=["AWS RDS", "Kafka"], skill_match="any"))


def test_year_bounds():
    person = profile(years_experience=3)
    assert not matches(person, filters(min_years=4, max_years=7))
    assert matches(person, filters(min_years=2, max_years=4))


def test_location_alias():
    person = profile(location="Bangalore")
    assert matches(person, filters(locations=["Bengaluru"]))
    assert not matches(person, filters(locations=["Berlin"]))


def test_company_history_current_past_and_any():
    person = profile(current_company_type="enterprise")
    spec = filters(company_types=["startup"])
    assert not matches(person, spec.model_copy(update={"company_history": "current"}))
    assert not matches(person, spec.model_copy(update={"company_history": "past"}))
    past_startup = profile(
        current_company_type="enterprise",
        past_companies=[PastCompany(company="Mango", company_type="startup", title="Engineer", years=1)],
    )
    assert matches(past_startup, spec.model_copy(update={"company_history": "past"}))
    assert matches(past_startup, spec.model_copy(update={"company_history": "any"}))
    assert not matches(past_startup, spec.model_copy(update={"company_history": "current"}))


def test_filter_profiles_returns_only_matches():
    people = [profile(id="a"), profile(id="b", location="Berlin")]
    found = filter_profiles(people, filters(locations=["Bangalore"]))
    assert [item.id for item in found] == ["a"]
