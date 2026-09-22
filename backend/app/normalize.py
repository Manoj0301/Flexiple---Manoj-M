import re

COMPANY_TYPES = ("startup", "scaleup", "enterprise", "agency")

COMPANY_TYPE_ALIASES = {
    "start-up": "startup",
    "start up": "startup",
    "early-stage": "startup",
    "early stage": "startup",
    "scale-up": "scaleup",
    "scale up": "scaleup",
}

SKILL_ALIASES: dict[str, set[str]] = {
    "rds": {"aws rds", "rds"},
    "aws rds": {"aws rds", "rds"},
    "postgres": {"postgresql", "postgres"},
    "postgresql": {"postgresql", "postgres"},
    "node": {"node.js", "nodejs", "node"},
    "nodejs": {"node.js", "nodejs", "node"},
    "node.js": {"node.js", "nodejs", "node"},
    "js": {"javascript", "js"},
    "javascript": {"javascript", "js"},
    "ts": {"typescript", "ts"},
    "typescript": {"typescript", "ts"},
    "k8s": {"kubernetes", "k8s"},
    "kubernetes": {"kubernetes", "k8s"},
    "golang": {"go", "golang"},
    "go": {"go", "golang"},
    "react.js": {"react", "react.js"},
    "react": {"react", "react.js"},
    "next": {"next.js", "nextjs", "next"},
    "next.js": {"next.js", "nextjs", "next"},
    "nextjs": {"next.js", "nextjs", "next"},
}

LOCATION_ALIASES: dict[str, set[str]] = {
    "bangalore": {"bangalore", "bengaluru"},
    "bengaluru": {"bangalore", "bengaluru"},
    "blr": {"bangalore", "bengaluru"},
    "delhi": {"delhi ncr", "delhi"},
    "delhi ncr": {"delhi ncr", "delhi"},
    "ncr": {"delhi ncr"},
    "gurgaon": {"delhi ncr"},
    "gurugram": {"delhi ncr"},
    "new delhi": {"delhi ncr"},
    "bombay": {"mumbai"},
    "mumbai": {"mumbai"},
    "madras": {"chennai"},
    "chennai": {"chennai"},
    "hyderabad": {"hyderabad"},
    "pune": {"pune"},
    "remote": {"remote - india", "remote"},
    "remote india": {"remote - india"},
    "remote - india": {"remote - india"},
    "amsterdam": {"amsterdam"},
    "berlin": {"berlin"},
}


def normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())


def coerce_company_type(value: str) -> str | None:
    key = normalize(value)
    key = COMPANY_TYPE_ALIASES.get(key, key)
    if key in COMPANY_TYPES:
        return key
    return None


def skill_tokens(value: str) -> set[str]:
    key = normalize(value)
    return set(SKILL_ALIASES.get(key, {key})) | {key}


def location_tokens(value: str) -> set[str]:
    key = normalize(value)
    return set(LOCATION_ALIASES.get(key, {key})) | {key}


def contains_text(haystack: str, quote: str) -> bool:
    hay = normalize(haystack)
    needle = normalize(quote)
    if not needle or not hay:
        return False
    if needle in hay:
        return True
    trimmed = re.sub(r"\b(years|yrs|year)\b", "", needle).strip()
    return bool(trimmed) and trimmed in hay
