# Method

## Audit task

An author runs a baseline experiment package and publishes a **record** containing:

- per-section hashes of the declared config;
- the declared seeds;
- SHA-256 fingerprints of five pipeline stages (`data`, `split`, `preprocess`, `model`, `metrics`);
- the metrics.

The **shipped** package may contain one mutation. An auditor receives the shipped package and the record and outputs:

- `flagged`: whether the result will fail to reproduce;
- `stage`: where the divergence first appears.

## Package format

| File | Purpose |
|---|---|
| `experiment.json` | Declared configuration |
| `.runtime_env.json` | Resolved environment (version of the simulated dependency `simlib`) |
| `.env` (optional) | Hidden overrides with keys `REPROMUT_OVERRIDE__<path>` |
| `.cache/preprocessed.npz` (optional) | Reused without key validation when `preprocess.use_cache` is true |

The runner never reads the real process environment.

## Methods

| Method | What it does |
|---|---|
| `no_audit` | Executes once. Never flags. |
| `seed_only` | Flags non-integer seeds or seeds that differ from the record. |
| `static_manifest` | Compares hashes of the declared config sections (`task`, `seeds`, `data`, `split`, `preprocess`, `model`, `evaluation`, `dependencies`). Cosmetic fields are excluded. Does not execute. |
| `dynamic` | Executes the package *k* = 2 times. Flags if the model/metrics fingerprints differ from the record or between runs. Localises to the earliest stage that differs from the record, otherwise the earliest unstable stage. |
| `combined` | Static OR dynamic. Uses the dynamic stage when dynamic flags. |

## Ground truth

Labels are declared per mutation. The oracle executes the mutant 3 times. It compares full arrays to the baseline and to each other (`atol = rtol = 1e-9`). A result change means the model or metrics stage diverged. The slow test suite requires 100% agreement with every declared label and stage.

## Fingerprints

Floats are rounded to 8 decimals, −0.0 and NaN are canonicalised, and integers are widened to int64. The hash covers dtype, shape and bytes.

Rounding can disagree with the tolerance oracle at rounding boundaries. Such disagreements would appear as dynamic-vs-oracle mismatches; none occurred in the development run.

## Statistics

- Wilson 95% intervals for proportions.
- A paired percentile bootstrap (2,000 resamples) for the recall difference.
- An exact McNemar test on discordant pairs.
