"""Turn user-typed values into numbers. Every parser returns None rather than guess."""
import re

_NUM = r"(\d[\d,]*(?:\.\d+)?|\.\d+)"


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _clean(text) -> str:
    return re.sub(r"\s+", " ", str(text)).strip().lower()


# ---------- money ----------
_INR_UNITS = {
    "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "l": 1e5, "lpa": 1e5, "lakh per annum": 1e5,
    "crore": 1e7, "crores": 1e7, "cr": 1e7,
    "k": 1e3, "thousand": 1e3, "hazar": 1e3, "hazaar": 1e3,
}
_INR = re.compile(
    rf"^(?:₹|rs\.?|inr)?\s*{_NUM}\s*({'|'.join(sorted(map(re.escape, _INR_UNITS), key=len, reverse=True))})?"
    r"\s*(?:rupees?|rupaye|rs\.?|/-|per annum|per year|p\.?a\.?|annually)?$"
)


def parse_inr(text) -> int | None:
    """'6.5 lakh', '6.5L', '₹6,50,000', '1.2 crore', '8 LPA' -> rupees. Bare small numbers -> None."""
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return int(text) if text >= 1000 else None
    m = _INR.match(_clean(text))
    if not m:
        return None
    value, unit = _num(m.group(1)), m.group(2)
    if unit:
        return int(round(value * _INR_UNITS[unit]))
    return int(value) if value >= 1000 else None  # "6.5" alone: lakh? thousand? don't guess


# ---------- grades ----------
_CGPA = re.compile(rf"^(?:cgpa|cpi|gpa|pointer)?\s*:?\s*{_NUM}\s*(?:/\s*10|out of 10)?\s*(?:cgpa|cpi|gpa|pointer)?$")
_PCT = re.compile(rf"^{_NUM}\s*(?:%|percent|percentage|pct|pratishat|प्रतिशत)$")


def parse_cgpa(text) -> float | None:
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return float(text) if 0 <= text <= 10 else None
    m = _CGPA.match(_clean(text))
    if not m:
        return None
    v = _num(m.group(1))
    return v if 0 <= v <= 10 else None


def parse_percentage(text) -> float | None:
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return float(text) if 0 <= text <= 100 else None
    m = _PCT.match(_clean(text))
    if not m:
        return None
    v = _num(m.group(1))
    return v if 0 <= v <= 100 else None


# ---------- year of study ----------
_ORDINALS = {
    "first": 1, "1st": 1, "pehla": 1, "pahla": 1, "pehle": 1, "पहला": 1, "पहले": 1,
    "second": 2, "2nd": 2, "doosra": 2, "dusra": 2, "doosre": 2, "dusre": 2, "दूसरा": 2, "दूसरे": 2,
    "third": 3, "3rd": 3, "teesra": 3, "tisra": 3, "teesre": 3, "तीसरा": 3, "तीसरे": 3,
    "fourth": 4, "4th": 4, "chautha": 4, "chotha": 4, "chauthe": 4, "चौथा": 4, "चौथे": 4,
    "fifth": 5, "5th": 5, "panchva": 5, "पाँचवां": 5,
}
_YEAR_WORD = r"(?:year|yr|saal|sal|varsh|साल|वर्ष)"


def parse_year(text) -> int | None:
    """'2nd year', 'second year', 'year 2', 'doosra saal' -> 2. 'final year' -> None (depends on programme)."""
    if isinstance(text, int) and not isinstance(text, bool):
        return text if 1 <= text <= 5 else None
    s = _clean(text)
    m = re.fullmatch(rf"(\S+)\s*{_YEAR_WORD}(?:\s*(?:mein|me|में))?", s)
    if m and m.group(1) in _ORDINALS:
        return _ORDINALS[m.group(1)]
    m = re.fullmatch(rf"{_YEAR_WORD}\s*([1-5])", s) or re.fullmatch(r"([1-5])", s)
    return int(m.group(1)) if m else None


# ---------- category ----------
_CATEGORIES = {
    "general": "GENERAL", "gen": "GENERAL", "open": "GENERAL", "ur": "GENERAL", "unreserved": "GENERAL",
    "ews": "EWS",
    "obc": "OBC_NCL", "obc-ncl": "OBC_NCL", "obc ncl": "OBC_NCL", "obc_ncl": "OBC_NCL",
    "obc (ncl)": "OBC_NCL", "obc non creamy layer": "OBC_NCL", "obc non-creamy layer": "OBC_NCL",
    "sc": "SC", "scheduled caste": "SC",
    "st": "ST", "scheduled tribe": "ST",
}


def parse_category(text) -> str | None:
    s = re.sub(r"\s*(category|caste|quota)$", "", _clean(text))
    return _CATEGORIES.get(s)


# ---------- yes / no ----------
_TRUE = {"yes", "y", "true", "haan", "haa", "han", "ha", "ji", "ji haan", "ji ha", "ha ji", "haan ji",
         "हाँ", "हां", "जी", "जी हाँ"}
_FALSE = {"no", "n", "false", "nahi", "nahin", "nai", "na", "nope", "ji nahi", "नहीं", "ना", "जी नहीं"}


def parse_bool(text) -> bool | None:
    if isinstance(text, bool):
        return text
    s = _clean(text).strip(".!")
    return True if s in _TRUE else False if s in _FALSE else None


# ---------- durations ----------
_DAY_UNITS = {
    "day": 1, "days": 1, "din": 1, "दिन": 1,
    "week": 7, "weeks": 7, "hafta": 7, "hafte": 7, "हफ्ते": 7, "सप्ताह": 7,
    "month": 30, "months": 30, "mahina": 30, "mahine": 30, "महीने": 30, "महीना": 30,  # ponytail: 30-day month
    "year": 365, "years": 365, "saal": 365, "साल": 365,
}
_DAYS = re.compile(rf"^{_NUM}\s*({'|'.join(sorted(map(re.escape, _DAY_UNITS), key=len, reverse=True))})$")


def parse_days(text) -> int | None:
    """'20 days' -> 20, '3 weeks' -> 21, '14 months' -> 420 (30-day months). Bare numbers -> None."""
    m = _DAYS.match(_clean(text))
    if not m:
        return None
    return int(round(_num(m.group(1)) * _DAY_UNITS[m.group(2)]))
