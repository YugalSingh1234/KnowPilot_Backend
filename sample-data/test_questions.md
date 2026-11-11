# Test questions

14 questions across both sample organizations (org1 = Navodaya Institute of Technology, org2 = Navyug Infotech). Machine-readable copy: `test_questions.json`; run them with `python scripts/run_eval.py`.

| # | Org | Category | Question | Status | Type | Outcome | Reference |
|---|---|---|---|---|---|---|---|
| 1 | org1 | direct | What is the re-evaluation fee per course? | answered | direct | - | NIT_Academic_Regulations.pdf |
| 2 | org1 | policy | What is the attendance rule for sitting the semester examination? | answered | policy | - | NIT_Academic_Regulations.pdf |
| 3 | org2 | procedural | How do I apply for leave and how many days in advance? | answered | procedural | - | Navyug_Leave_Policy.pdf |
| 4 | org1 | comparison | What is the difference between the merit-cum-means scholarship and the sports excellence scholarship? | answered | comparison | - | NIT_Scholarship_Policy_2025-26.pdf |
| 5 | org1 | multi-condition ELIGIBLE | I am in 3rd year B.Tech, CGPA 8.2, family income 6 lakh, attendance 85%, and I get no other scholarship. Am I eligible for the merit-cum-means scholarship? | answered | eligibility | ELIGIBLE | NIT_Scholarship_Policy_2025-26.pdf |
| 6 | org1 | multi-condition NOT_ELIGIBLE | I am in 2nd year, CGPA 8.2, income 6.5 lakh, attendance 80%, but I already get a UP post-matric scholarship. Am I eligible for merit-cum-means? | answered | eligibility | NOT_ELIGIBLE | NIT_Scholarship_Policy_2025-26.pdf |
| 7 | org1 | NEEDS_MORE_INFO | My CGPA is 8.5 and my family income is 5 lakh. Can I get the merit-cum-means scholarship? | answered | eligibility | NEEDS_MORE_INFO | NIT_Scholarship_Policy_2025-26.pdf |
| 8 | org2 | Hinglish | Probation ke dauran earned leave ka kya rule hai? | answered | policy | - | Navyug_Leave_Policy.pdf |
| 9 | org1 | not in KB | What is the JEE Main cutoff for CSE this year? | no_answer | any | - | - |
| 10 | org2 | not in KB | What is the company's work from home policy for Fridays? | no_answer | any | - | - |
| 11 | org1 | cross-tenant | How many days of earned leave does an employee get at Navyug Infotech? | no_answer | any | - | - |
| 12 | org2 | cross-tenant | What is the merit-cum-means scholarship award amount at Navodaya Institute of Technology? | no_answer | any | - | - |
| 13 | org1 | direct | What is the hostel fee per year? | answered | direct | - | NIT_Admission_and_Fee_Rules.pdf |
| 14 | org2 | policy | What happens to earned leave above 30 days at year end? | answered | policy | - | Navyug_Leave_Policy.pdf |

Cross-tenant rows (11, 12) ask one org about the other org's data and must return `no_answer` with no references.
