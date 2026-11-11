# Evaluation results

Run against `http://localhost:8000` on 2026-11-11. **13/14 passed.**

| # | Category | Expected (status / type / outcome / ref) | Got (status / type / outcome / refs) | Result |
|---|---|---|---|---|
| 1 | direct | answered / direct / - / NIT_Academic_Regulations.pdf | answered / direct / - / NIT_Academic_Regulations.pdf | PASS |
| 2 | policy | answered / policy / - / NIT_Academic_Regulations.pdf | answered / policy / - / NIT_Academic_Regulations.pdf | PASS |
| 3 | procedural | answered / procedural / - / Navyug_Leave_Policy.pdf | answered / procedural / - / Navyug_Leave_Policy.pdf | PASS |
| 4 | comparison | answered / comparison / - / NIT_Scholarship_Policy_2025-26.pdf | answered / comparison / - / NIT_Scholarship_Policy_2025-26.pdf | PASS |
| 5 | multi-condition ELIGIBLE | answered / eligibility / ELIGIBLE / NIT_Scholarship_Policy_2025-26.pdf | answered / eligibility / NEEDS_MORE_INFO / NIT_Scholarship_Policy_2025-26.pdf | FAIL (outcome) |
| 6 | multi-condition NOT_ELIGIBLE | answered / eligibility / NOT_ELIGIBLE / NIT_Scholarship_Policy_2025-26.pdf | answered / eligibility / NOT_ELIGIBLE / NIT_Scholarship_Policy_2025-26.pdf | PASS |
| 7 | NEEDS_MORE_INFO | answered / eligibility / NEEDS_MORE_INFO / NIT_Scholarship_Policy_2025-26.pdf | answered / eligibility / NEEDS_MORE_INFO / NIT_Scholarship_Policy_2025-26.pdf | PASS |
| 8 | Hinglish | answered / policy / - / Navyug_Leave_Policy.pdf | answered / policy / - / Navyug_Leave_Policy.pdf | PASS |
| 9 | not in KB | no_answer / - / - / - | no_answer / out_of_scope / - / - | PASS |
| 10 | not in KB | no_answer / - / - / - | no_answer / policy / - / - | PASS |
| 11 | cross-tenant | no_answer / - / - / - | no_answer / policy / - / - | PASS |
| 12 | cross-tenant | no_answer / - / - / - | no_answer / direct / - / - | PASS |
| 13 | direct | answered / direct / - / NIT_Admission_and_Fee_Rules.pdf | answered / direct / - / NIT_Admission_and_Fee_Rules.pdf | PASS |
| 14 | policy | answered / policy / - / Navyug_Leave_Policy.pdf | answered / policy / - / Navyug_Leave_Policy.pdf | PASS |
