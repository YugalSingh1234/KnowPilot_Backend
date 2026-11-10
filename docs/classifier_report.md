# Question-type classifier report

Generated 2026-11-11 by `scripts/train_classifier.py`.

- Data: `app/system1/data/question_types.csv`, 160 rows
  (comparison 25, direct 25, eligibility 25, out_of_scope 35, policy 25, procedural 25).
- Model: word TF-IDF (1-2) + char_wb TF-IDF (2-5) -> LogisticRegression (class_weight=balanced).
- Fallback: predictions below 0.40 confidence become `policy`.
- Saved to `app/system1/models/question_classifier.joblib` (trained on all rows).

## 5-fold cross-validation (each row predicted by a model that did not see it)

```
              precision    recall  f1-score   support

  comparison      0.818     0.720     0.766        25
      direct      0.731     0.760     0.745        25
 eligibility      0.800     0.800     0.800        25
out_of_scope      0.862     0.714     0.781        35
      policy      0.750     0.840     0.792        25
  procedural      0.733     0.880     0.800        25

    accuracy                          0.781       160
   macro avg      0.782     0.786     0.781       160
weighted avg      0.787     0.781     0.781       160
```
