import joblib
import numpy as np

model = joblib.load("data_storage/models/global_rf_v4.pkl")
print("Model type:", type(model))
print("Classes:", getattr(model, "classes_", None))
if hasattr(model, "calibrated_classifiers_"):
    print("Calibrated classifiers count:", len(model.calibrated_classifiers_))
