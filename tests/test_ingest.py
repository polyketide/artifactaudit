"""Inventory, classification and read-coverage. Fixtures are synthetic temp files."""
import os

from sciguard.ingest import classify, coverage, inventory


def test_classify_by_extension():
    assert classify("model.pdb") == "structure"
    assert classify("reads.fasta") == "seq"
    assert classify("notes.md") == "text"
    assert classify("deck.pptx") == "slides"
    assert classify("paper.pdf") == "pdf"
    assert classify("table.xlsx") == "sheet"
    assert classify("panel.png") == "image"
    assert classify("mystery.qqq") == "other"
    assert classify("no-extension") == "other"


def _tree(tmp_path):
    (tmp_path / "a.md").write_text("hello", encoding="utf-8")
    (tmp_path / "b.pdb").write_text("ATOM", encoding="utf-8")
    (tmp_path / ".DS_Store").write_text("junk", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.png").write_bytes(b"\x89PNG")
    return tmp_path


def test_inventory_recurses_and_skips_junk(tmp_path):
    inv = inventory(str(_tree(tmp_path)))
    rels = sorted(e["rel"] for e in inv)
    assert rels == ["a.md", "b.pdb", os.path.join("sub", "c.png")]
    assert ".DS_Store" not in repr(inv)


def test_inventory_marks_what_cannot_be_text_extracted(tmp_path):
    inv = {e["rel"]: e for e in inventory(str(_tree(tmp_path)))}
    assert inv["a.md"]["extractable"] is True
    assert inv["b.pdb"]["extractable"] is False      # a structure file needs a viewer, not a text read
    assert inv["b.pdb"]["how"]


def test_coverage_names_what_was_not_read(tmp_path):
    root = _tree(tmp_path)
    cov = coverage(str(root), [str(root / "a.md")])
    assert cov["total_files"] == 3
    assert cov["read"] == 1
    assert cov["coverage"] == round(1 / 3, 3)
    not_read = {e["rel"] for e in cov["not_read"]}
    assert "b.pdb" in not_read
    assert cov["unextractable_total"] >= 2           # the .pdb and the .png
