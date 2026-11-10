"""Train the question-type classifier, print a report, save the model and docs/classifier_report.md.

    python scripts/train_classifier.py
"""
import csv
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import joblib  # noqa: E402
from sklearn.metrics import classification_report  # noqa: E402
from sklearn.model_selection import StratifiedKFold, cross_val_predict  # noqa: E402

from app.system1.classifier import DATA_PATH, MODEL_PATH, build_pipeline  # noqa: E402

with open(DATA_PATH, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
texts, labels = [r["text"] for r in rows], [r["label"] for r in rows]

# Honest estimate: every row is predicted by a model that never saw it (5-fold CV).
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
predicted = cross_val_predict(build_pipeline(), texts, labels, cv=cv)
report = classification_report(labels, predicted, digits=3, zero_division=0)
print(report)

model = build_pipeline().fit(texts, labels)
MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
joblib.dump(model, MODEL_PATH)
print("saved", MODEL_PATH.relative_to(ROOT))

counts = Counter(labels)
(ROOT / "docs" / "classifier_report.md").write_text(
    f"""# Question-type classifier report

Generated {date.today().isoformat()} by `scripts/train_classifier.py`.

- Data: `app/system1/data/question_types.csv`, {len(rows)} rows
  ({", ".join(f"{k} {v}" for k, v in sorted(counts.items()))}).
- Model: word TF-IDF (1-2) + char_wb TF-IDF (2-5) -> LogisticRegression (class_weight=balanced).
- Fallback: predictions below 0.40 confidence become `policy`.
- Saved to `app/system1/models/question_classifier.joblib` (trained on all rows).

## 5-fold cross-validation (each row predicted by a model that did not see it)

```
{report}```
""",
    encoding="utf-8",
)
print("wrote docs/classifier_report.md")
