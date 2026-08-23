# Third-party notices — Tenis AI AutoLearn v8.4A

## CatBoost
CatBoost is developed by Yandex and contributors and is distributed under the Apache License 2.0.
Tenis AI uses the Python `catboost` package as the primary tabular meta-ranker.

## TabPFN
TabPFN is developed by Prior Labs GmbH and contributors.
Tenis AI v8.4A is explicitly configured to request **TabPFN model version V2** through
`TabPFNClassifier.create_default_for_version(ModelVersion.V2)`.
It does not intentionally select the package default or the newer V2.5/V2.6/V3 checkpoints.
Use and redistribution remain subject to the license shipped by Prior Labs for the code and
model weights. The challenger is fail-open: if the package/checkpoint cannot be used, Tenis AI
continues with Current Engine + CatBoost.
