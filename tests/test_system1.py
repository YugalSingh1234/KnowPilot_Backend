import pytest

from app.system1 import language, normalizer as nz
from app.system1.answerability import is_answerable
from app.system1.classifier import LABELS, classify


# ---------- normalizer ----------
@pytest.mark.parametrize("text, expected", [
    ("6.5 lakh", 650000), ("6.5L", 650000), ("₹6,50,000", 650000), ("1.2 crore", 12000000),
    ("8 LPA", 800000), ("Rs. 8,00,000", 800000), ("5 lac", 500000), ("₹ 50,000", 50000),
    ("7 lakh rupees", 700000), ("50k", 50000), ("2 cr", 20000000), (800000, 800000),
    ("6.5", None), ("bahut zyada", None), ("", None),
])
def test_parse_inr(text, expected):
    assert nz.parse_inr(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("8.2", 8.2), ("8.2 CGPA", 8.2), ("CGPA 7.5", 7.5), ("8.5/10", 8.5), ("7 pointer", 7.0),
    ("82", None), ("eight", None),
])
def test_parse_cgpa(text, expected):
    assert nz.parse_cgpa(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("78%", 78.0), ("78 percent", 78.0), ("72.5 %", 72.5), ("80 pratishat", 80.0), ("120%", None), ("78", None),
])
def test_parse_percentage(text, expected):
    assert nz.parse_percentage(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("2nd year", 2), ("second year", 2), ("doosra saal", 2), ("dusre saal mein", 2), ("year 3", 3),
    ("3rd yr", 3), ("teesra saal", 3), ("4th year", 4), ("दूसरा साल", 2), ("final year", None), ("7th year", None),
])
def test_parse_year(text, expected):
    assert nz.parse_year(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("General", "GENERAL"), ("ews", "EWS"), ("OBC-NCL", "OBC_NCL"), ("obc", "OBC_NCL"), ("SC category", "SC"),
    ("ST", "ST"), ("obc creamy layer", None), ("brahmin", None),
])
def test_parse_category(text, expected):
    assert nz.parse_category(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("yes", True), ("haan", True), ("Haan ji", True), ("हाँ", True), ("no", False), ("nahi", False),
    ("nahin", False), ("नहीं", False), ("maybe", None), ("shayad", None),
])
def test_parse_bool(text, expected):
    assert nz.parse_bool(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("20 days", 20), ("3 weeks", 21), ("14 months", 420), ("10 din", 10), ("2 hafte", 14), ("1 saal", 365),
    ("20", None), ("kuch din", None),
])
def test_parse_days(text, expected):
    assert nz.parse_days(text) == expected


# ---------- language ----------
@pytest.mark.parametrize("text, expected", [
    ("What is the hostel fee?", "en"),
    ("mujhe scholarship milegi kya", "hinglish"),
    ("hostel fee kitna hai", "hinglish"),
    ("मुझे छात्रवृत्ति मिलेगी?", "hi"),
    ("Is the CGPA rule same for all?", "en"),
    ("mera CGPA 8 hai", "hinglish"),
])
def test_language(text, expected):
    assert language.detect(text) == expected


# ---------- answerability gate (GATE_MIN_SIMILARITY = 0.55 from settings) ----------
def _chunks(vector, keyword=0.0):
    return [{"vector_score": vector, "keyword_score": keyword}]


def test_gate():
    assert is_answerable(_chunks(0.70))["answerable"] is True
    assert is_answerable(_chunks(0.50, keyword=0.3))["answerable"] is True   # keyword-assisted
    assert is_answerable(_chunks(0.50, keyword=0.0))["answerable"] is False
    assert is_answerable(_chunks(0.40, keyword=1.0))["answerable"] is False
    assert is_answerable([]) == {"answerable": False, "confidence": 0.0}


# ---------- classifier ----------
def test_classifier_loads_and_predicts():
    result = classify("I am in 3rd year with CGPA 8 and income 5 lakh, am I eligible for the merit scholarship?")
    assert result["label"] in LABELS and 0 <= result["confidence"] <= 1
    assert result["label"] == "eligibility"
    assert classify("Tell me a joke about cricket")["label"] == "out_of_scope"
    assert classify("re-evaluation ke liye apply kaise kare")["label"] == "procedural"
