# E2 licence review

**Status: DRAFT.** Reviewed from the licence files at the recorded commit SHAs, read as text. This is not legal advice.

## Policy

- **Code licences.** Only MIT, BSD-2-Clause, BSD-3-Clause and Apache-2.0 are allowed. GitHub's SPDX detection was cross-checked against the licence file at the pinned commit.
- **What we do with third-party code.** We run it locally in isolated containers. We do not vendor, modify, redistribute or publish it. ReproMut stores only URLs, commit SHAs, licence metadata, our own adapter code and the outputs we derive.
- **Apache-2.0 obligations.** These (NOTICE, statement of changes) apply only to redistribution, which we do not do.
- **Dataset licences.** These are reviewed separately from code licences; a permissive code licence does **not** license the data shipped with it. Under amendment A1, every dataset fetched at build time gets a record here (source URL, SHA-256, licence) before it is used.
- **Author decision, 2026-11-09.** Committed datasets with no stated licence may be used for local execution only. Only aggregate derived metrics are reported, and the data is never redistributed.

## Eligible repositories

| Repository | Code licence | Data | Data licence | Restrictions |
|---|---|---|---|---|
| fmind/mlops-python-package | MIT (`LICENSE.txt`) | UCI Bike Sharing (`data/hour.csv`, committed) | **CC BY 4.0**, confirmed on the UCI dataset page (id 275, DOI 10.24432/C5W894) on 2026-11-09 | Cite Fanaee-T (2013) if derived results are published |
| AmirhosseinHonardoust/Subscription-Loyalty-Risk-Radar | MIT (`LICENSE`) | `data/raw/shopping_behavior.csv` (Kaggle-derived, committed) | Not stated | Local use only; aggregate metrics only (author decision) |
| sagnik1511/Tabular-AutoML | see manifest (`LICENSE`) | `tab_automl/datasets/Iris.csv`, `wine.csv` (committed; UCI-origin datasets) | The committed copies state no licence | Local use only; aggregate metrics only (author decision) |
| youngcoder45/Student-Performance-Predictor | see manifest | UCI Student Performance (id 320), `student.zip` fetched at build time | **Pending.** The UCI page fetch timed out on 2026-11-09. Record the licence and SHA-256 before the build. | Only if the licence permits local research use |
| ARUNAGIRINATHAN-K/Text-Classifier-using-NLP_Techniques | MIT | `data/sample_data.csv` (committed, origin not stated) + NLTK punkt/stopwords (fetched at build) | Not stated / NLTK data licences to be recorded at build | Local use only; aggregate metrics only |
| roodriigoooo/clustering_the_vrp | MIT | Augerat CVRP instances (committed) | Not stated | Local use only; aggregate metrics only |
| jaideepsinhdabhi/JustDataML | Apache-2.0 | `examples/Data/bezdekIris.data` (committed) | UCI Iris: CC BY 4.0 at source | Cite UCI if derived results are published |
| Bruce-Lee-LY/machine_learning | MIT | synthetic (`make_blobs`) | n/a | none |
| nazmul-1117/bangladesh-air-pollution-pattern-mining | MIT | `data/raw/air_quality.csv` (committed; Kaggle-derived) | Not stated (the README itself says to check redistribution terms) | Local use only; aggregate metrics only |
| chonzadaniel/Model-Deployment-Using-Flask | MIT | `salaryprediction_data.csv` (committed; UCI Adult-derived) | Not stated in the repository (UCI Adult is CC BY 4.0 at source) | Local use only; aggregate metrics only |
| andi611/Naive-Bayes-and-Decision-Tree-Classifiers | MIT | `data.zip` (committed; Mushroom subset used) | Not stated in the repository (UCI Mushroom is CC BY 4.0 at source) | Local use only; aggregate metrics only |
| thaije/capteam-iglo-titanic-ml | MIT | `Data/*.csv` (committed; Kaggle Titanic) | Not stated | Local use only; aggregate metrics only |
| NHLOCAL/is-this-bible | MIT | `data_creation/bible_data.csv` (committed) + NLTK stopwords (fetched at build) | Not stated | Local use only; aggregate metrics only |
| AmirhosseinHonardoust/Fake-Review-Detector | MIT | `data/reviews_sample.csv` (committed, origin not stated) | Not stated | Local use only; aggregate metrics only |

Code licences for the P3 repositories were taken from GitHub's SPDX detection at the pinned commit and cross-checked against the licence file during manual review. The full table, with commit SHAs, is in `REPOSITORY-MANIFEST.json`.

## Excluded for licence or data reasons

- **Data obtainable only through external tools or services:** Arabic-OCR (`.rar`), kedro-snowflake, the Azure templates, qgate-sln-mlrun.
- **Data from live APIs or with no stated licence (A1 review):** mlb_game_predictor, cf-difficulty-prediction, scikit-llm, descubreplayas, yt-watch-history, ab-testing-in-ml (Reddit comments, no licence), hands-on-train-and-deploy-ml, using_chatgpt_kedro_streamlit_app.
- **GitHub licence detection disagreeing with the licence file:** none found.

## Open items

1. Student Performance dataset licence and archive SHA-256. This is only needed if the study proceeds.
