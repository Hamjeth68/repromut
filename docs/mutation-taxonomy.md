# Mutation taxonomy (v0.1)

Run `repromut list-mutations` for the authoritative list. **Stage** is where the oracle first observes divergence.

## Result-changing mutations (positive)

| ID | Family | Stage | Applies to | Visible in config? |
|---|---|---|---|---|
| seed_unset | random-state | data | all | yes |
| seed_time_derived | random-state | data | all | yes |
| split_seed_changed | random-state | split | supervised | yes |
| row_order_changed | data-order | data | regression | yes |
| dependency_default_drift | dependency | preprocess | scale-sensitive models | **no** (runtime env) |
| env_override | hidden-config | model | all | **no** (`.env`) |
| dtype_float32 | numeric | data | non-tree models | yes |
| stale_cache | caching | preprocess | all | **no** (`.cache/`) |
| train_eval_mismatch | config-mismatch | preprocess | supervised | yes |
| label_noise_changed | data-generation | data | all | yes |
| feature_generation_changed | data-generation | data | all | yes |
| solver_tolerance_loosened | numeric | model | logreg, sgd_reg, kmeans | yes |

## Semantics-preserving controls

`run_name_changed`, `output_dir_changed`, `notes_added`, `log_level_changed`, `config_key_order_changed` (all cosmetic), `thread_count_changed` (RF/KNN only), and `dependency_patch_bump`.

## Invariances found by the oracle during development

These were found before freezing. Each is interesting in its own right, because the input changes but the result does not:

1. **Label-sorted rows plus a stratified split.** Stratified shuffling with a stable sort selects the same rows, so classification results reproduce exactly even though the data-stage artifacts differ. The mutation was restricted to unstratified (regression) tasks.
2. **float32 features with tree ensembles.** Split thresholds are unaffected at this data scale, so random forests reproduce exactly. The mutation was restricted to non-tree models.
3. **Loosened tolerance with GMM on separated clusters.** EM converges within one iteration, so the result is unchanged. GMM was excluded.

A candidate for v0.2: turn these into "hard controls", meaning intermediate artifacts change but the result does not. They specifically stress auditors that compare intermediate artifacts too strictly.
