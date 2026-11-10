# Question-type classifier report

Generated 2026-11-10 by `scripts/train_classifier.py`.

- Data: `app/system1/data/question_types.csv`, 150 rows
  (comparison 25, direct 25, eligibility 25, out_of_scope 25, policy 25, procedural 25).
- Model: word TF-IDF (1-2) + char_wb TF-IDF (2-5) -> LogisticRegression (class_weight=balanced).
- Fallback: predictions below 0.40 confidence become `policy`.
- Saved to `app/system1/models/question_classifier.joblib` (trained on all rows).

## 5-fold cross-validation (each row predicted by a model that did not see it)

```
              precision    recall  f1-score   support

  comparison      0.818     0.720     0.766        25
      direct      0.690     0.800     0.741        25
 eligibility      0.800     0.800     0.800        25
out_of_scope      0.765     0.520     0.619        25
      policy      0.750     0.840     0.792        25
  procedural      0.759     0.880     0.815        25

    accuracy                          0.760       150
   macro avg      0.764     0.760     0.756       150
weighted avg      0.764     0.760     0.756       150
```
