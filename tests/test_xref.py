"""Cross-reference / placeholder auditing. Fixtures are synthetic."""
from sciguard.xref import audit_references, extract_refs, format_audit


def test_unfilled_placeholders_are_flagged():
    a = audit_references("Methods in Figure Sx; deposited as PDB [ID]; data are n = [3].")
    assert any("[ID]" in p for p in a["placeholders"])
    assert len(a["placeholders"]) >= 2


def test_cited_but_absent_and_present_but_uncited_figures():
    a = audit_references(
        "Figure 1 shows the fold; see Figure 2 and Figure 5A; cf. Fig S21 for the controls.",
        figure_labels=["Figure 1", "Figure 2", "Figure 4", "Figure 5"])
    # Equality, not membership: a tolerant "in" assertion stayed green while the reference regex was
    # dropping every panel-lettered citation, so the suite could not catch a relapse.
    assert a["referenced"] == ["Figure 1", "Figure 2", "Figure 5", "Figure S21"]
    assert a["missing_figures"] == ["Figure S21"]        # cited in text, not in the figure set
    assert a["unreferenced_figures"] == ["Figure 4"]     # in the set, never cited (off-by-one class)


def test_accession_placeholder_flagged_but_a_poly_x_sequence_is_not():
    acc = audit_references("deposited under the accession numbers AB123456 and LCxxxxxx, respectively")
    seq = audit_references("the modelled segment MKAXXXXQ and four molecules per asymmetric unit")
    assert "LCxxxxxx" in acc["placeholders"]
    assert not seq["placeholders"]


def test_fill_me_in_question_marks_but_not_a_real_interrogative():
    full = audit_references("pending affiliation ？？ to be supplied")
    latin = audit_references("Is the mechanism really concerted?? We tested it.")
    cjk = audit_references("これは何ですか？？")  # lang:ok — a real JP interrogative must NOT flag
    assert full["placeholders"] == ["？？"]
    assert not latin["placeholders"]
    assert not cjk["placeholders"]


def test_extract_refs_normalises_the_label():
    refs = extract_refs("as in Fig. 3 and Table S1")
    assert "Figure 3" in refs and "Table S1" in refs


def test_format_audit_is_printable():
    out = format_audit(audit_references("no references here"))
    assert "Reference audit" in out


def test_a_panel_letter_still_counts_as_citing_the_figure():
    # "Figure 5A" cites Figure 5. A regex that demands a word boundary right after the number drops
    # every panel-lettered citation, which inverts the headline check: a figure that IS discussed is
    # reported as never referenced.
    for text, want in [("Figure 5A", "Figure 5"), ("Fig. 2b", "Figure 2"),
                       ("Table 3A", "Table 3"), ("Scheme 2c", "Scheme 2"),
                       ("Figure S4B", "Figure S4")]:
        assert extract_refs(text) == [want]
    a = audit_references("only Fig. 3a is discussed", figure_labels=["Figure 3"])
    assert a["unreferenced_figures"] == []


def test_plural_and_abbreviated_labels_match():
    assert extract_refs("Figures 3") == ["Figure 3"]
    assert extract_refs("Figs. 3") == ["Figure 3"]
    assert extract_refs("Tables 2") == ["Table 2"]


def test_a_longer_number_is_not_truncated():
    # The original guard: "Figure 1234" must not match as "Figure 123".
    assert extract_refs("Figure 1234") == []


def test_known_limits_are_pinned_not_silently_wrong():
    # Documented in README under scope and honesty: a list or a range cites only its first figure.
    # Pinned here so the limit is a decision, not a surprise.
    assert extract_refs("Figures 4 and 5") == ["Figure 4"]
    assert extract_refs("Figs. 2-4") == ["Figure 2"]
