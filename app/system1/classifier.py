"""Question-type classifier (scikit-learn). Trained by scripts/train_classifier.py."""
from functools import lru_cache
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer

HERE = Path(__file__).resolve().parent
DATA_PATH = HERE / "data" / "question_types.csv"
MODEL_PATH = HERE / "models" / "question_classifier.joblib"
LABELS = ("direct", "policy", "procedural", "eligibility", "comparison", "out_of_scope")
MIN_CONFIDENCE = 0.40
FALLBACK = "policy"


def build_pipeline() -> Pipeline:
    return Pipeline([
        ("features", FeatureUnion([
            ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), lowercase=True, sublinear_tf=True)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), lowercase=True, sublinear_tf=True)),
        ])),
        ("clf", LogisticRegression(class_weight="balanced", max_iter=2000, C=5.0)),
    ])


@lru_cache
def _model() -> Pipeline:
    # joblib uses pickle: safe here only because MODEL_PATH is our own artifact, built by
    # scripts/train_classifier.py and committed. Never point this at a user-supplied file.
    return joblib.load(MODEL_PATH)


def classify(text: str) -> dict:
    """-> {"label", "confidence"}. Below MIN_CONFIDENCE the label falls back to 'policy'."""
    model = _model()
    proba = model.predict_proba([text])[0]
    best = int(proba.argmax())
    label, confidence = str(model.classes_[best]), float(proba[best])
    if confidence < MIN_CONFIDENCE:
        label = FALLBACK
    return {"label": label, "confidence": round(confidence, 3)}
