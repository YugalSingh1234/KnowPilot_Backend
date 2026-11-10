# Sample data

Two **fictional** organizations used for demos and testing. Every PDF says "Illustrative policy for
a fictional organization" in its footer. The rules are explicit and numeric so eligibility questions
have clear answers.

| Org | Login | PDFs |
|---|---|---|
| **Navodaya Institute of Technology, Kanpur**: engineering college | `admin@navodaya.test` / `Demo@12345` | `org1/`: Scholarship Policy 2025-26, Admission and Fee Rules, Academic Regulations |
| **Navyug Infotech Pvt. Ltd., Pune**: IT company | `hr@navyug.test` / `Demo@12345` | `org2/`: Leave Policy, Employee Handbook, Benefits Policy |

Key facts for testing (Navodaya): Merit-cum-Means needs B.Tech year 2-4, CGPA >= 7.5,
family income <= ₹8,00,000, no other scholarship (state post-matric / NSP), attendance >= 75%;
"Percentage equivalent = CGPA x 9.5" is on its own page.

## Regenerate the PDFs

```
.venv\Scripts\activate
pip install -r sample-data/requirements.txt
python sample-data/generate_pdfs.py
```

The script needs a TrueType font with the ₹ sign (Arial on Windows, DejaVu Sans on Linux).

## Seed the demo organizations

With the API running (`uvicorn app.main:app --port 8000`):

```
python scripts/seed_demo.py
```

It registers both orgs (or logs in if they exist), uploads any PDFs not yet uploaded and prints each
assistant URL. It is safe to run again. To re-upload a changed PDF, delete it in the dashboard first.
