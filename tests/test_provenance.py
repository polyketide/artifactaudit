"""Source-of-record gating. Fixtures are synthetic."""
from artifactaudit.provenance import audit_memory, classify_source, require_source


def test_a_sealed_lab_notebook_entry_is_primary():
    # The id scheme is configurable (LEDGER_ID / LEDGER_FILE_HINT); the default matches a generic
    # "<PREFIX>-<number>" and a filename that says notebook or ledger.
    assert classify_source("NB-0042")[0] == "primary"
    assert classify_source("lab_notebook.md")[0] == "primary"


def test_something_that_is_not_an_id_is_not_promoted_to_primary():
    assert classify_source("notes")[0] != "primary"


def test_audit_memory_refuses_the_wrong_type_instead_of_passing():
    # It used to return a PASSING audit for anything without .active(), including None — a gate that
    # cannot fail. Pinned so it cannot regress to silence.
    import pytest
    for bad in (None, [], {"findings": []}, "a string"):
        with pytest.raises(TypeError):
            audit_memory(bad)


def test_a_raw_data_filename_is_primary():
    assert classify_source("hplc_raw_trace.csv")[0] == "primary"


def test_a_draft_or_summary_is_derived():
    assert classify_source("manuscript_draft.docx")[0] == "derived"
    assert classify_source("group_meeting_report.pptx")[0] == "derived"


def test_an_empty_source_classifies_as_none():
    assert classify_source("")[0] == "none"
    assert classify_source(None)[0] == "none"


def test_a_finding_without_a_source_is_blocked():
    ok, why = require_source({"text": "kcat is 3.2 per second", "source": None})
    assert ok is False and "BLOCKING" in why


def test_a_quantitative_claim_on_a_derived_source_warns_but_passes():
    ok, why = require_source({"text": "kcat is 3.2 per second", "source": "manuscript_draft.docx"})
    assert ok is True and "[CHECK]" in why


def test_a_qualitative_claim_on_a_derived_source_does_not_warn():
    ok, why = require_source({"text": "the fold is a TIM barrel", "source": "manuscript_draft.docx"})
    assert ok is True and "[CHECK]" not in why


def test_audit_memory_sweeps_a_store():
    class Store:
        def active(self, kind):
            return [{"text": "kcat is 3.2 per second", "source": None},
                    {"text": "kcat is 3.2 per second", "source": "manuscript_draft.docx"},
                    {"text": "the fold is a TIM barrel", "source": "EJ-0007"}]

    a = audit_memory(Store())
    assert a["findings"] == 3
    assert len(a["unsourced"]) == 1
    assert len(a["weak_source"]) == 1
    assert a["ok"] is False
