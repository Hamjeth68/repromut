# Verified scikit-learn default changes (M-DEP / C-DEP candidates)

Each change was checked on 2026-11-09 against the official versioned scikit-learn API documentation.

| Estimator / parameter | Old → new default | Version | Source (quoted) |
|---|---|---|---|
| `KMeans(n_init=…)` | 10 → `'auto'` | 1.4 | `https://scikit-learn.org/1.5/modules/generated/sklearn.cluster.KMeans.html`: "Changed in version 1.4: Default value for `n_init` changed to `'auto'`." |
| `LinearSVC(dual=…)` | `True` → `'auto'` | 1.5 | `https://scikit-learn.org/1.5/modules/generated/sklearn.svm.LinearSVC.html`: "The `"auto"` option is added in version 1.3 and will be the default in version 1.5." |
| `TSNE(learning_rate=…)` | 200.0 → `'auto'` | 1.2 | `https://scikit-learn.org/1.5/modules/generated/sklearn.manifold.TSNE.html`: "Changed in version 1.2: The default value changed to `"auto"`." |
| `TSNE(init=…)` | `'random'` → `'pca'` | 1.2 | same page: "Changed in version 1.2: The default value changed to `"pca"`." |
| `AdaBoostClassifier(algorithm=…)` | `'SAMME.R'` → `'SAMME'` | 1.6 | `https://scikit-learn.org/1.5/modules/generated/sklearn.ensemble.AdaBoostClassifier.html`: default `'SAMME.R'`; "Deprecated since version 1.4: "SAMME.R" is deprecated and will be removed in version 1.6." The 1.6 page lists only `'SAMME'` as the default. |
| `PCA(svd_solver='auto')` policy | auto-selection policy changed | 1.5 | scikit-learn 1.5 release notes (verified earlier in the session) |

Removed: the RandomForest/ExtraTrees Regressor `max_features` change in 1.1 was a rename with no change in behaviour (DEVIATIONS S3).

**What this table does not establish.** A documented default change is not a positive mutation by itself. Under the protocol, the oracle decides whether a version swap actually changes the defined result for each repository.
