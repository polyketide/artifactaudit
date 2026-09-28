"""Cross-artifact numeric reconciliation. Fixtures are synthetic."""
from artifactaudit.reconcile import extract_mutant_values, extract_mz, reconcile, reconcile_mutants

MAIN = "K72A was nearly inactive in our hands. D145N retained 40% activity."
SI = "K72A 10% ; D145N 4%"


def _flags(**kw):
    return {(f["mutant"], f["type"]) for f in reconcile_mutants({"main": MAIN, "SI": SI}, **kw)["flags"]}


def test_qualitative_text_versus_numeric_si_is_flagged():
    # "nearly inactive" in prose, 10% in the SI chart: the contradiction a reader never sees.
    assert ("K72A", "qual_vs_numeric") in _flags()


def test_numeric_disagreement_beyond_tolerance_is_flagged():
    assert ("D145N", "numeric_mismatch") in _flags()


def test_extract_mutant_values_reads_the_window_after_the_label():
    vals = extract_mutant_values(MAIN)
    assert "D145N" in vals and "K72A" in vals


def test_extract_mz():
    assert 412.7 in extract_mz("the product gave m/z 412.7 in positive mode")


def test_reconcile_flags_a_shared_key_that_disagrees():
    out = reconcile({"main": {"m/z": 412.7, "resolution": 2.75},
                     "SI": {"m/z": 188.3, "resolution": 2.75}})
    keys = {f.get("key") for f in out}
    assert "m/z" in keys          # 412.7 vs 188.3 disagrees
    assert "resolution" not in keys   # identical values must not be flagged


def test_identical_sources_produce_no_flags():
    assert reconcile({"a": {"kcat": 3.2}, "b": {"kcat": 3.2}}) == []


def test_a_reagent_formula_is_not_mistaken_for_a_mutant():
    # H2O and D2O have the shape of a mutant label, so the bare pattern used to treat them as mutants
    # and could then report a numeric_mismatch between two solvent percentages.
    vals = extract_mutant_values("the buffer was 90% H2O and 10% D2O; K72A retained 40% activity")
    assert set(vals) == {"K72A"}
    flags = reconcile_mutants({"main": "run in 90% H2O", "SI": "run in 50% H2O"})["flags"]
    assert flags == []
