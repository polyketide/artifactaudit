"""Source ingestion + coverage (slot V, input side) — "did I actually read everything?"

The blind spot: when an agent reads a folder it silently reads the files it *judges* relevant and
skips the rest (figures inside .pptx, .png images, structure and instrument files, archives,
whole subfolders) — and even a text extraction that yields 0 chars passes unnoticed. A missed
source is invisible, so "I analysed the folder" is unfalsifiable unless coverage is reported.

This module makes ingestion auditable, the mirror of eval/coverage.py:
- `inventory(root)` enumerates EVERY file (recursive), classifies it, and says whether its text is
  programmatically extractable or needs a specialized/visual tool.
- `extract_text(path)` dispatches per type — incl. a real .pptx extractor (slide XML text + image
  count), so an image-only figure deck is reported as "image-only, needs visual inspection" rather
  than a silent 0.
- `coverage(root, read_paths)` reports total vs. read, and the explicit **NOT-READ list with a
  reason** — so a folder analysis must declare what it skipped.

Pure classification/parsers are unit-testable offline; extraction shells out (textutil) / uses
openpyxl only when actually called.
"""
from __future__ import annotations

import json
import os
import re
import subprocess

# extension → category (first match wins). Lowercase, no dot.
_CATEGORY = {
    "text": {"txt", "md", "csv", "tsv", "json", "xml", "yaml", "yml", "log"},
    "seq": {"fasta", "fa", "fna", "faa", "dna", "gb", "genbank", "ape", "praln", "aln"},
    "doc": {"docx", "doc", "rtf"},
    "pdf": {"pdf"},
    "slides": {"pptx", "ppt", "key"},
    "sheet": {"xlsx", "xls"},
    "image": {"png", "jpg", "jpeg", "tif", "tiff", "gif", "bmp", "svg", "heic"},
    "structure": {"pdb", "cif", "mmcif", "mol", "mol2", "sdf", "mae", "pse", "cdxml", "cdx"},
    "data": {"prism", "pzfx", "cys", "xgmml", "dat", "mtz", "ccp4", "map"},
    "archive": {"zip", "tar", "gz", "tgz", "bz2", "7z", "rar"},
}
# categories whose text we CAN pull programmatically here (pdf = best-effort via poppler/pypdf;
# a scanned/image PDF still yields 0 chars and is flagged needs-OCR, never silently dropped)
_EXTRACTABLE = {"text", "seq", "doc", "slides", "sheet", "pdf"}
_SKIP_NAMES = {".DS_Store", "Thumbs.db", ".gitkeep"}


def classify(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    for cat, exts in _CATEGORY.items():
        if ext in exts:
            return cat
    return "other"


def _how(cat: str) -> str:
    return {
        "text": "read directly", "seq": "read directly (sequence/alignment)",
        "doc": "textutil → txt", "slides": "unzip slide XML (text + image count)",
        "sheet": "openpyxl rows", "pdf": "pdftotext/pypdf → txt (scanned/image PDFs flagged needs-OCR)",
        "image": "VISUAL — needs the Read tool / OCR; cannot read as text",
        "structure": "specialized (PyMOL/parser); note-only here",
        "data": "specialized (Prism/Cytoscape/etc.); note-only here",
        "archive": "unzip first, then re-inventory", "other": "unknown — inspect manually",
    }.get(cat, "inspect manually")


def inventory(root: str) -> list[dict]:
    """Every file under root (recursive), classified. Skips junk + dotfiles."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            if fn in _SKIP_NAMES or fn.startswith("."):
                continue
            cat = classify(fn)
            full = os.path.join(dirpath, fn)
            try:
                size = os.path.getsize(full)
            except OSError:
                size = -1
            out.append({"path": full, "rel": os.path.relpath(full, root), "category": cat,
                        "size": size, "extractable": cat in _EXTRACTABLE, "how": _how(cat)})
    out.sort(key=lambda r: r["rel"])
    return out


# ---- text extraction (incl. the formats that get silently dropped) --------------

def _strip_xml(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def pptx_text(path: str) -> dict:
    """Slide-XML text + image count from a .pptx — what textutil often misses (returns 0)."""
    import zipfile
    try:
        with zipfile.ZipFile(path) as z:
            slides = sorted(n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n))
            texts, images = [], 0
            for n in slides:
                xml = z.read(n).decode("utf-8", "ignore")
                texts.append(_strip_xml(xml))
                images += len(re.findall(r"<a:blip", xml))
            text = "\n".join(t for t in texts if t)
            return {"ok": True, "category": "slides", "n_slides": len(slides),
                    "images": images, "chars": len(text), "text": text,
                    "note": ("image-only deck — needs VISUAL inspection (Read tool)"
                             if len(text) < 20 and images else "ok")}
    except Exception as e:
        return {"ok": False, "category": "slides", "error": f"{type(e).__name__}: {e}"}


def ocr_pdf(path: str, langs: str = "jpn+eng", dpi: int = 200, max_pages: int = 30) -> dict:
    """OFFLINE OCR for a scanned/image PDF: poppler `pdftoppm` rasterises pages → `tesseract` reads
    them (Japanese+English by default). Zero token, zero network — but slow (~seconds/page), so it is
    OPT-IN, not part of the bulk sweep. The result is flagged ocr=True (lower confidence: OCR can
    misread); never fabricated. `max_pages` bounds runtime on long scans."""
    import glob
    import shutil
    import tempfile
    if not (shutil.which("pdftoppm") and shutil.which("tesseract")):
        return {"ok": False, "category": "pdf",
                "error": "OCR unavailable — install poppler (pdftoppm) + tesseract (`brew install tesseract tesseract-lang`)"}
    with tempfile.TemporaryDirectory() as td:
        pref = os.path.join(td, "pg")
        try:
            subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-l", str(max_pages), path, pref],
                           capture_output=True, timeout=600, check=False)
        except Exception as e:
            return {"ok": False, "category": "pdf", "error": f"pdftoppm: {type(e).__name__}: {e}"}
        pages = sorted(glob.glob(pref + "*.png"))
        texts = []
        for p in pages:
            try:
                texts.append(subprocess.run(["tesseract", p, "stdout", "-l", langs],
                                             capture_output=True, text=True, timeout=180).stdout)
            except Exception:
                pass
        text = "\n".join(texts).strip()
        if text:
            return {"ok": True, "category": "pdf", "chars": len(text), "text": text, "ocr": True,
                    "note": f"ok (OCR tesseract {langs}, {len(pages)} page(s) — verify, OCR may misread)"}
        return {"ok": False, "category": "pdf", "chars": 0, "text": "", "note": "OCR produced no text"}


def pdf_text(path: str, ocr: bool = False) -> dict:
    """Offline PDF text — poppler `pdftotext` (preferred), else `pypdf`. A scanned/image PDF yields
    ~0 chars; with `ocr=True` it falls back to OCR (pdftoppm+tesseract, offline), otherwise it is
    flagged **needs-OCR** (NOT a silent empty, NOT off-topic). Nothing is ever fabricated."""
    import shutil

    def _scanned():
        return (ocr_pdf(path) if ocr else
                {"ok": False, "category": "pdf", "chars": 0, "text": "",
                 "note": "scanned/image PDF — 0 extractable chars, needs OCR (pass ocr=True)"})

    if shutil.which("pdftotext"):
        try:
            t = subprocess.run(["pdftotext", "-q", path, "-"],
                               capture_output=True, text=True, timeout=120).stdout
            if t.strip():
                return {"ok": True, "category": "pdf", "chars": len(t), "text": t, "note": "ok (pdftotext)"}
            return _scanned()
        except Exception as e:
            return {"ok": False, "category": "pdf", "error": f"pdftotext: {type(e).__name__}: {e}"}
    try:
        import pypdf
        reader = pypdf.PdfReader(path)
        t = "\n".join((pg.extract_text() or "") for pg in reader.pages)
        if t.strip():
            return {"ok": True, "category": "pdf", "chars": len(t), "text": t, "note": "ok (pypdf)"}
        return _scanned()
    except ImportError:
        return {"ok": False, "category": "pdf",
                "error": "no local PDF extractor — install poppler (`brew install poppler`) or `pip install pypdf`"}
    except Exception as e:
        return {"ok": False, "category": "pdf", "error": f"pypdf: {type(e).__name__}: {e}"}


def extract_text(path: str, ocr: bool = False) -> dict:
    """Best-effort text for one file; flag-not-fabricate for non-text types. `ocr=True` enables the
    offline OCR fallback for scanned PDFs (slow; opt-in)."""
    cat = classify(os.path.basename(path))
    if cat == "pdf":
        return pdf_text(path, ocr=ocr)
    if cat in ("text", "seq"):
        try:
            return {"ok": True, "category": cat, "text": open(path, encoding="utf-8", errors="ignore").read()}
        except Exception as e:
            return {"ok": False, "category": cat, "error": str(e)}
    if cat == "doc":
        try:
            t = subprocess.run(["textutil", "-convert", "txt", "-stdout", path],
                               capture_output=True, text=True, timeout=60).stdout
            return {"ok": bool(t.strip()), "category": cat, "chars": len(t), "text": t,
                    "note": "ok" if t.strip() else "textutil returned 0 — inspect manually"}
        except Exception as e:
            return {"ok": False, "category": cat, "error": str(e)}
    if cat == "slides":
        return pptx_text(path)
    if cat == "sheet":
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
            rows = sum(ws.max_row or 0 for ws in wb.worksheets)
            return {"ok": True, "category": cat, "sheets": [ws.title for ws in wb.worksheets],
                    "rows": rows, "note": "use the xlsx dumper to read cell values"}
        except Exception as e:
            return {"ok": False, "category": cat, "error": str(e)}
    return {"ok": False, "category": cat, "note": _how(cat),
            "error": f"{cat}: not auto-extractable as text — {_how(cat)}"}


# ---- ingestion coverage (the audit) ---------------------------------------------

def coverage(root: str, read_paths: list[str]) -> dict:
    """What fraction of the folder was actually read, and the explicit NOT-READ list with reasons."""
    inv = inventory(root)
    read_abs = {os.path.realpath(p) for p in read_paths}
    by_cat: dict[str, dict] = {}
    not_read = []
    for f in inv:
        c = f["category"]
        by_cat.setdefault(c, {"total": 0, "read": 0})
        by_cat[c]["total"] += 1
        if os.path.realpath(f["path"]) in read_abs:
            by_cat[c]["read"] += 1
        else:
            not_read.append({"rel": f["rel"], "category": c,
                             "why": ("not yet read" if f["extractable"] else f"needs: {f['how']}")})
    total = len(inv)
    n_read = total - len(not_read)
    return {"root": root, "total_files": total, "read": n_read,
            "coverage": round(n_read / total, 3) if total else None,
            "by_category": by_cat, "not_read": not_read,
            "unextractable_total": sum(1 for f in inv if not f["extractable"])}


def format_inventory(inv: list[dict]) -> str:
    cats: dict[str, list[dict]] = {}
    for f in inv:
        cats.setdefault(f["category"], []).append(f)
    lines = [f"Source inventory — {len(inv)} files"]
    for cat in sorted(cats):
        fs = cats[cat]
        mark = "✓ text" if cat in _EXTRACTABLE else "✗ needs special handling"
        lines.append(f"  [{cat}] {len(fs)} files — {mark} ({_how(cat)})")
        for f in fs:
            lines.append(f"      {f['rel']}  ({f['size']}B)")
    nonx = [f for f in inv if not f["extractable"]]
    if nonx:
        lines.append(f"\n  ⚠ {len(nonx)} files are NOT auto-extractable as text "
                     f"(image / structure / data / pdf / archive) — these are the silent-miss risk:")
        lines += [f"      {f['rel']} [{f['category']}]" for f in nonx]
    return "\n".join(lines)
