import asyncio

from app.system1.decisions import engine
from app.system1.decisions.schemas import Choice, Condition, Conversions, DecisionSpec

SRC = {"filename": "NIT_Scholarship_Policy_2025-26.pdf", "page": 1}


def merit_conditions():
    return [
        Condition(id="year", label="B.Tech year 2-4", field="year", operator="in", value=[2, 3, 4],
                  value_type="year", source=SRC),
        Condition(id="cgpa", label="CGPA >= 7.5", field="cgpa", operator=">=", value=7.5, value_type="cgpa", source=SRC),
        Condition(id="income", label="Income <= ₹8,00,000", field="family_income", operator="<=",
                  value="₹8,00,000", value_type="inr", source=SRC),
        Condition(id="other", label="No other scholarship", field="other_scholarship", operator="==",
                  value=False, value_type="bool", source=SRC),
        Condition(id="attendance", label="Attendance >= 75%", field="attendance", operator=">=", value=75,
                  value_type="percentage", source=SRC),
    ]


FACTS = {"year": "2nd year", "cgpa": "8.2", "family_income": "6.5 lakh", "other_scholarship": "nahi",
         "attendance": "80%"}


def run(spec):
    return asyncio.run(engine.run(spec))


def test_eligible():
    r = run(DecisionSpec(user_facts=FACTS, conditions=merit_conditions()))
    assert r["outcome"] == "ELIGIBLE" and r["missing_facts"] == [] and r["score"] == 100
    assert all(c["result"] == "TRUE" for c in r["conditions"])
    assert r["conditions"][2]["user_value"] == 650000


def test_not_eligible_because_of_other_scholarship():
    facts = {**FACTS, "other_scholarship": "haan"}  # already gets NSP
    r = run(DecisionSpec(user_facts=facts, conditions=merit_conditions()))
    assert r["outcome"] == "NOT_ELIGIBLE"
    failed = [c for c in r["conditions"] if c["result"] == "FALSE"]
    assert [c["id"] for c in failed] == ["other"] and failed[0]["source"] == SRC


def test_needs_more_info_when_income_missing():
    facts = {k: v for k, v in FACTS.items() if k != "family_income"}
    r = run(DecisionSpec(user_facts=facts, conditions=merit_conditions()))
    assert r["outcome"] == "NEEDS_MORE_INFO" and r["missing_facts"] == ["family_income"]
    assert r["score"] == 90  # 4 TRUE + 1 UNKNOWN (half) out of 5


def test_false_beats_unknown():
    facts = {k: v for k, v in FACTS.items() if k != "family_income"} | {"cgpa": "7.0"}
    assert run(DecisionSpec(user_facts=facts, conditions=merit_conditions()))["outcome"] == "NOT_ELIGIBLE"


def test_first_year_not_eligible():
    r = run(DecisionSpec(user_facts={**FACTS, "year": "pehla saal"}, conditions=merit_conditions()))
    assert r["outcome"] == "NOT_ELIGIBLE"


def test_cgpa_to_percentage_only_with_document_multiplier():
    cond = [Condition(id="pct", label=">= 70%", field="percentage", operator=">=", value=70, value_type="percentage")]
    with_mult = run(DecisionSpec(user_facts={"cgpa": "8"}, conditions=cond,
                                 conversions=Conversions(cgpa_to_percentage=9.5)))
    assert with_mult["outcome"] == "ELIGIBLE" and with_mult["conditions"][0]["user_value"] == 76.0
    without = run(DecisionSpec(user_facts={"cgpa": "8"}, conditions=cond))
    assert without["outcome"] == "NEEDS_MORE_INFO" and without["missing_facts"] == ["percentage"]


def test_choice_picks_first_fully_true_option():
    choices = [
        Choice(id="mcm", label="Merit-cum-Means", criteria=merit_conditions()),
        Choice(id="sports", label="Sports Excellence", criteria=[
            Condition(id="medal", label="State medal", field="state_medal", operator="==", value=True, value_type="bool"),
        ]),
    ]
    facts = {**FACTS, "other_scholarship": "yes", "state_medal": "haan"}
    r = run(DecisionSpec(user_facts=facts, conditions=merit_conditions(), choices=choices))
    assert r["choice"] == {"choice_id": "sports", "label": "Sports Excellence"}


def test_failing_evaluator_becomes_unknown_and_timings_recorded():
    def boom(spec):
        raise RuntimeError("broken")

    spec = DecisionSpec(user_facts=FACTS, conditions=merit_conditions())
    r = asyncio.run(engine.run(spec, evaluators_override={"boolean": boom}))
    assert r["outcome"] == "NEEDS_MORE_INFO"  # no crash; boolean became UNKNOWN
    assert r["score"] == 100  # the other evaluators still ran
    timings = {t["decision"]: t for t in r["timings"]}
    assert set(timings) == {"boolean", "choice", "score"}
    assert timings["boolean"]["error"] == "RuntimeError"
    assert all(t["end_ms"] >= t["start_ms"] >= 0 for t in timings.values())


def test_bad_condition_value_is_unknown_not_crash():
    cond = [Condition(id="x", label="weird", field="cgpa", operator=">=", value="not a number", value_type="cgpa")]
    r = run(DecisionSpec(user_facts={"cgpa": "8"}, conditions=cond))
    assert r["outcome"] == "NEEDS_MORE_INFO"
