# Related work

Status: first pass done on 2026-11-08 using targeted web searches. This is **not yet a systematic review**; a full search is still planned (see the source and query lists at the bottom). The full references are in `paper/references.bib`.

## Closest work — must be addressed in any submission

**Shulepov (2026), arXiv:2608.27100.** *Mutation Testing for Reproducibility Safeguards in Machine Learning Research Software: An Empirical Study.* It introduces the tool MLReproMutate.

- **What it does:** applies 4 mutation classes (seed, dependency pin, data split, CV fold count) to real ML repositories and checks whether the repositories' *existing* validation workflows catch them. It reports 2 of 23 detected.
- **How ReproMut differs:**
  - synthetic experiments with ground truth confirmed by an oracle;
  - 12 operators, including 3 hidden ones (cache, `.env`, dependency drift);
  - 7 semantics-preserving controls, which make it possible to measure false-positive rates;
  - a comparison of auditor *classes*, including localisation and cost.
- **Relationship:** complementary. Note the similar names: consider renaming ReproMut before public release to avoid confusion.

So far, only the abstract has been read. Read the full paper before submitting.

## Other cited work (each checked against at least one bibliographic source)

- **Reproducibility in AI and ML:**
  - Gundersen & Kjensmo (AAAI 2018)
  - Pineau et al. (JMLR 2021)
  - Bouthillier et al. (MLSys 2021)
  - Zhuang et al. (MLSys 2022)
  - Kapoor & Narayanan (Patterns 2023)
- **Executability of research code:**
  - Pimentel et al. (MSR 2019)
  - Trisovic et al. (Scientific Data 2022)
  - ReproZip (Chirigati et al., SIGMOD 2016)
- **Mutation and metamorphic testing:**
  - Jia & Harman (TSE 2011)
  - Xie et al. (JSS 2011)
  - DeepMutation (Ma et al., ISSRE 2018)
  - Dutta et al., "To Seed or Not to Seed?" (ICST 2022)

## Still to do

Run a systematic search of ACM DL, IEEE Xplore, DBLP, arXiv, Google Scholar, GitHub, PyPI, Zenodo and patent databases. Use query terms covering reproducibility mutation testing, ML experiment provenance and artifact hashing, and computational reproducibility auditing tools.
