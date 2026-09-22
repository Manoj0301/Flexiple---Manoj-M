from app.evidence import infer_citations, validate_citations
from app.models import Citation, Profile
from tests.test_filters import profile


def test_accepts_verbatim_skill_and_years():
    person = profile()
    kept = validate_citations(
        person,
        [
            Citation(field="skills", quote="AWS RDS"),
            Citation(field="years_experience", quote="6 years"),
            Citation(field="skills", quote="Kafka"),
        ],
    )
    assert [item.quote for item in kept] == ["AWS RDS", "6 years"]


def test_rejects_unknown_field():
    person = profile()
    assert validate_citations(person, [Citation(field="salary", quote="100")]) == []


def test_infer_citations_from_reason():
    person: Profile = profile()
    found = infer_citations(person, "Ananya has AWS RDS experience at NimbusPay in Bangalore.")
    quotes = {item.quote for item in found}
    assert "AWS RDS" in quotes
    assert "NimbusPay" in quotes
    assert "Bangalore" in quotes
