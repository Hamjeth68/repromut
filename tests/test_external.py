import ast

from repromut import external as X

SRC = '''
import numpy as np
from sklearn.model_selection import train_test_split, KFold
from sklearn.ensemble import RandomForestClassifier
np.random.seed(0)
rng = np.random.RandomState(42)
X, y = np.arange(20).reshape(10, 2), np.arange(10) % 2
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=1)
clf = RandomForestClassifier(n_estimators=10, random_state=3)
kf = KFold(n_splits=5)
print("accuracy", 0.95)
print("Fit time: 0.12s")
'''


def test_extract_numbers_skips_timing_lines():
    assert X.extract_numbers("acc 0.5 f1=0.25\nelapsed 3.2\ndone in 0.1s\nn = 7") == [0.5, 0.25, 7.0]


def test_seed_removed_and_changed():
    removed = X.seed_removed(SRC)
    assert removed is not None and "random_state=None" in removed and "RandomState()" in removed
    changed = X.seed_changed(SRC)
    assert "random_state=2" in changed and "RandomState(43)" in changed and "seed(1)" in changed
    assert X.seed_removed("print(1)") is None


def test_split_cv_iterations():
    assert "test_size=0.3" in X.split_changed(SRC)
    assert "n_splits=6" in X.cv_changed(SRC)
    assert "n_estimators=5" in X.iterations_reduced(SRC)
    assert X.split_changed("print(1)") is None


def test_controls_are_semantically_identical():
    assert X.semantic_hash(X.comment_added(SRC)) == X.semantic_hash(SRC)
    assert X.semantic_hash(X.reformatted(SRC)) == X.semantic_hash(SRC)
    assert X.semantic_hash(X.seed_changed(SRC)) != X.semantic_hash(SRC)


def test_seed_literals_and_auditors():
    rec = {"seeds": X.seed_literals(SRC), "semantic_hash": X.semantic_hash(SRC)}
    assert rec["seeds"] == [0, 42, 1, 3]
    assert X.audit_seed_only(X.seed_removed(SRC), rec)
    assert not X.audit_seed_only(X.split_changed(SRC), rec)
    assert X.audit_static(X.split_changed(SRC), rec)
    assert not X.audit_static(X.reformatted(SRC), rec)


def test_run_script_and_oracle_end_to_end():
    src = "import numpy as np\nnp.random.seed(0)\nprint(np.random.rand())\n"
    out = X.run_script(src, timeout=30)
    assert out.ok and len(out.numbers) == 1
    base = [out, X.run_script(src, timeout=30)]
    assert X.numbers_close(base[0].numbers, base[1].numbers)
    op_ctrl = next(o for o in X.OPERATORS if o.id == "comment_added")
    assert not X.oracle(X.comment_added(src), base, op_ctrl)["result_changed"]
    op_seed = next(o for o in X.OPERATORS if o.id == "seed_changed")
    assert X.oracle(X.seed_changed(src), base, op_seed)["result_changed"]


def test_run_script_fixes_python_hash_seed():
    out = X.run_script(
        "import os\nprint(os.environ['PYTHONHASHSEED'])\n",
        timeout=30,
        env_extra={"PYTHONHASHSEED": "123"},
    )
    assert out.ok and out.numbers == [0.0]


def test_sampling_is_deterministic():
    p = [f"f{i}.py" for i in range(20)]
    assert X.sample_order(p, "x") == X.sample_order(list(reversed(p)), "x")
    assert X.sample_order(p, "x") != X.sample_order(p, "y")


def test_failed_script_reported():
    assert not X.run_script("raise SystemExit(3)", timeout=10).ok
    assert ast.parse(X.reformatted(SRC))
