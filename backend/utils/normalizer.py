"""
Normalization Utilities

Shared text normalization functions used across cleaner and insights modules.
"""

import re
from rapidfuzz import fuzz, process


# ---------------------------------------------------------------------------
# Company Name Normalization
# ---------------------------------------------------------------------------

# Common suffixes to strip for matching purposes
_COMPANY_SUFFIXES = re.compile(
    r"\b(pvt\.?|private|ltd\.?|limited|inc\.?|incorporated|llp|llc|"
    r"corp\.?|corporation|co\.?|company|enterprises?|solutions?|"
    r"technologies|tech|infra|infrastructure|group)\b",
    re.IGNORECASE,
)


def normalize_company_name(name: str) -> str:
    """
    Normalize a company name for matching/dedup.
    - Lowercase
    - Strip common suffixes (Pvt, Ltd, Inc, etc.)
    - Collapse whitespace
    - Strip leading/trailing whitespace and punctuation
    """
    if not name or not isinstance(name, str):
        return ""
    
    result = name.lower().strip()
    result = _COMPANY_SUFFIXES.sub("", result)
    result = re.sub(r"[.\-,&]+", " ", result)  # Replace punctuation with space
    result = re.sub(r"\s+", " ", result).strip()  # Collapse whitespace
    return result


# ---------------------------------------------------------------------------
# Sector Normalization
# ---------------------------------------------------------------------------

# Known canonical sector names and their common aliases
SECTOR_ALIASES = {
    "renewables": ["renewable", "renewables", "renewable energy", "solar", "wind energy", "clean energy", "green energy"],
    "energy": ["energy", "power", "thermal", "oil & gas", "oil and gas", "petroleum"],
    "infrastructure": ["infrastructure", "infra", "construction", "civil", "roads", "highways"],
    "mining": ["mining", "mines", "minerals", "quarry"],
    "agriculture": ["agriculture", "agri", "farming", "agritech", "agri-tech"],
    "telecom": ["telecom", "telecommunications", "telco", "communication"],
    "real estate": ["real estate", "realty", "property", "housing"],
    "government": ["government", "govt", "public sector", "defence", "defense", "military"],
    "technology": ["technology", "it", "information technology", "info tech", "software", "saas"],
    "logistics": ["logistics", "supply chain", "transportation", "transport", "shipping"],
    "manufacturing": ["manufacturing", "industrial", "factory"],
    "survey": ["survey", "surveying", "land survey", "geospatial"],
    "oil & gas": ["oil & gas", "oil and gas", "o&g", "petroleum", "refinery"],
    "urban development": ["urban development", "urban planning", "smart city", "smart cities", "urban"],
}

# Build a reverse lookup: alias -> canonical name
_ALIAS_TO_CANONICAL = {}
for canonical, aliases in SECTOR_ALIASES.items():
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias.lower()] = canonical


def normalize_sector(sector: str) -> str:
    """
    Normalize a sector name to its canonical form.
    Uses exact alias lookup first, then fuzzy matching.
    """
    if not sector or not isinstance(sector, str):
        return "Unknown"
    
    cleaned = sector.lower().strip()
    
    # Direct alias match
    if cleaned in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[cleaned]
    
    # Fuzzy match against all known aliases
    all_aliases = list(_ALIAS_TO_CANONICAL.keys())
    if all_aliases:
        match = process.extractOne(cleaned, all_aliases, scorer=fuzz.ratio, score_cutoff=70)
        if match:
            return _ALIAS_TO_CANONICAL[match[0]]
    
    # Return title-cased original if no match
    return sector.strip().title()


def fuzzy_match_sector(sector: str, known_sectors: list[str], threshold: int = 70) -> str:
    """
    Match a sector string against a list of known sector names.
    Returns the best match above threshold, or None.
    """
    if not sector or not known_sectors:
        return None
    
    match = process.extractOne(sector, known_sectors, scorer=fuzz.ratio, score_cutoff=threshold)
    return match[0] if match else None
