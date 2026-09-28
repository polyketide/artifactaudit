"""The one hard no-upload line: a registry of sequences that must never be transmitted.

Default-open by design — with no registry nothing is confidential, so the guard cannot silently block
ordinary work. But an EXPLICITLY configured registry that is missing fails CLOSED, because a mistyped
path must not read as "nothing is confidential".

Every sequence below is invented for the test. They are deliberately not real tags or real vectors:
a published expression-tag sequence would make the "all fixtures are synthetic" claim false.
"""
import pytest

from sciguard import confidential

SEQ = "MQWRTYKLPDGEAVNHSFICQWRTYKLPDGEA"
OTHER = "MLPDQWKRTYNGHEAVSFICMLPDQWKRTYNG"


def _use(monkeypatch, path):
    monkeypatch.setenv("ENZYME_CONFIDENTIAL_SEQS", str(path))
    confidential.reload_registry()


def _reg(tmp_path, body, name="confidential-seqs.txt"):
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_default_open_when_nothing_is_configured(monkeypatch, tmp_path):
    monkeypatch.delenv("ENZYME_CONFIDENTIAL_SEQS", raising=False)
    monkeypatch.chdir(tmp_path)          # no ./state/confidential-seqs.txt here
    confidential.reload_registry()
    assert confidential.is_confidential(SEQ) is False


def test_an_explicitly_configured_registry_that_is_missing_fails_closed(monkeypatch, tmp_path):
    # The failure this pins: a typo in the path used to yield an empty protected set, so the guard was
    # off and reported nothing. Silence is the one answer it must never give.
    _use(monkeypatch, tmp_path / "typo.txt")
    with pytest.raises(FileNotFoundError):
        confidential.is_confidential(SEQ)


def test_a_registered_sequence_is_refused(monkeypatch, tmp_path):
    _use(monkeypatch, _reg(tmp_path, "# private\n>unpublished-1\n" + SEQ + "\n"))
    assert confidential.is_confidential(SEQ) is True


def test_an_unregistered_sequence_still_passes(monkeypatch, tmp_path):
    _use(monkeypatch, _reg(tmp_path, SEQ + "\n"))
    assert confidential.is_confidential(OTHER) is False


def test_a_pasted_fragment_is_caught_too(monkeypatch, tmp_path):
    _use(monkeypatch, _reg(tmp_path, SEQ + "\n"))
    assert confidential.is_confidential(SEQ[5:30]) is True


def test_fasta_headers_case_and_line_breaks_are_ignored(monkeypatch, tmp_path):
    _use(monkeypatch, _reg(tmp_path, ">x\n" + SEQ[:16] + "\n" + SEQ[16:] + "\n"))
    assert confidential.is_confidential(SEQ.lower()) is True


def test_the_twenty_letter_floor_is_real_in_both_directions(monkeypatch, tmp_path):
    # Documented, not incidental: a query below the floor is never confidential, and a registry entry
    # below the floor is discarded rather than honoured.
    _use(monkeypatch, _reg(tmp_path, SEQ + "\nSHORTENTRY\n"))
    assert confidential.is_confidential(SEQ[:10]) is False
    assert confidential.is_confidential("SHORTENTRY") is False


def test_the_cwd_registry_is_found_without_any_environment_variable(monkeypatch, tmp_path):
    # The README tells a reader to create ./state/confidential-seqs.txt. Resolving only against the
    # installed package put that file outside the search path, so a correctly-followed README produced
    # a guard that was silently off.
    monkeypatch.delenv("ENZYME_CONFIDENTIAL_SEQS", raising=False)
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "confidential-seqs.txt").write_text(SEQ + "\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    confidential.reload_registry()
    assert confidential.is_confidential(SEQ) is True


def test_registry_path_reports_whether_it_was_configured(monkeypatch, tmp_path):
    reg = _reg(tmp_path, SEQ + "\n")
    _use(monkeypatch, reg)
    path, explicit = confidential.registry_path()
    assert path == str(reg) and explicit is True
    monkeypatch.delenv("ENZYME_CONFIDENTIAL_SEQS", raising=False)
    assert confidential.registry_path()[1] is False


def test_editing_the_registry_is_picked_up(monkeypatch, tmp_path):
    # The cache is keyed on (path, mtime); a one-slot cache keyed on nothing returned the earlier,
    # empty answer forever once anything had asked a question.
    reg = _reg(tmp_path, "PLACEHOLDERSEQUENCEAAAAAAAA\n")
    _use(monkeypatch, reg)
    assert confidential.is_confidential(SEQ) is False
    reg.write_text(SEQ + "\n", encoding="utf-8")
    confidential.reload_registry()
    assert confidential.is_confidential(SEQ) is True
