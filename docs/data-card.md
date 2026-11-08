# Data card

- **Source:** generated at run time by scikit-learn generators (`make_classification`, `make_regression`, `make_blobs`). Regression and clustering features also get a per-feature random rescale and shift.
- **Seeds:** every seed is `sha256("20261108/<experiment>/<role>")[:4]`, read as a big-endian integer, where role is `data`, `split` or `model`.
- **Size:** 400 samples per experiment. 10 features (classification and regression) or 5 features (clustering).
- **People:** no real persons, records or personal data of any kind.
- **Licence:** generated fixtures are offered under CC0. The generator code is under Apache-2.0.
- **Intended use:** benchmarking reproducibility-auditing methods.
- **Not for:** drawing conclusions about real-world model performance, sensor data, or any application domain.
- **Known biases:** generator data are cleaner and more Gaussian than real data. Cluster structure is idealised.
