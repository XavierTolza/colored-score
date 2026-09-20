"""Tests de la génération PDF (pdf_generator.py)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from abc_parser import parse_abc  # noqa: E402
from config import load_config  # noqa: E402
from pdf_generator import PDFGenerator  # noqa: E402


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def _make_score(text: str):
    return parse_abc(text, load_config())


def test_generates_pdf_file(cfg, tmp_path):
    score = _make_score("X:1\nT:Test\nM:4/4\nL:1/4\nK:C\nC D E F |]\n")
    out = tmp_path / "test.pdf"
    PDFGenerator(cfg).generate(score, str(out))
    assert out.is_file()
    assert out.stat().st_size > 1000
    with open(out, "rb") as fh:
        assert fh.read(5) == b"%PDF-"


def test_staff_position_mapping(cfg):
    """Vérifie la conversion note -> position sur la portée (Do4..Do5)."""
    gen = PDFGenerator(cfg)
    expected = {"C": -1.0, "D": -0.5, "E": 0.0, "F": 0.5,
                "G": 1.0, "A": 1.5, "B": 2.0, "c": 2.5}
    for note in cfg.ordered_notes():
        assert gen._staff_position(note) == expected[note.abc]


def test_all_colors_present_in_pdf(cfg, tmp_path):
    """Les 8 couleurs du clavier doivent toutes être rendues dans le PDF.

    On rasterise la page et on vérifie que chaque couleur cible existe dans
    l'image produite (toutes les touches de la gamme sont sur une seule page).
    """
    pypdfium2 = pytest.importorskip("pypdfium2")
    score = _make_score("X:1\nT:Gamme\nM:4/4\nL:1/4\nK:C\nC D E F G A B c |]\n")
    out = tmp_path / "colors.pdf"
    PDFGenerator(cfg).generate(score, str(out))

    page = pypdfium2.PdfDocument(str(out))[0]
    img = page.render(scale=2).to_pil().convert("RGB")
    pixels = set(img.getdata())

    for note in cfg.ordered_notes():
        target = tuple(round(v * 255) for v in note.rgb)
        # Tolérance : on cherche une couleur proche (antialiasing / arrondis).
        found = any(
            abs(px[0] - target[0]) <= 6
            and abs(px[1] - target[1]) <= 6
            and abs(px[2] - target[2]) <= 6
            for px in pixels
        )
        assert found, f"Couleur {note.color} ({note.label_en}) absente du rendu"


def test_page_size_from_config(tmp_path):
    cfg = load_config()
    cfg.raw["layout"]["page_size"] = "A5"
    gen = PDFGenerator(cfg)
    from reportlab.lib.pagesizes import A5
    assert (round(gen.page_w), round(gen.page_h)) == (round(A5[0]), round(A5[1]))


def test_landscape_orientation(tmp_path):
    cfg = load_config()
    cfg.raw["layout"]["orientation"] = "landscape"
    gen = PDFGenerator(cfg)
    assert gen.page_w > gen.page_h


def test_ledger_line_positions(cfg):
    """Do4 nécessite une ligne supplémentaire ; Sol4 non."""
    gen = PDFGenerator(cfg)
    assert gen._staff_position(cfg.note_by_abc("C")) == -1.0
    assert gen._staff_position(cfg.note_by_abc("G")) == 1.0


def test_multipage_for_long_score(cfg, tmp_path):
    """Une partition très longue produit plusieurs pages."""
    measure = "C D E F G A B c " * 12
    abc = f"X:1\nT:Long\nM:4/4\nL:1/4\nK:C\n{measure}|]\n"
    score = _make_score(abc)
    out = tmp_path / "long.pdf"
    PDFGenerator(cfg).generate(score, str(out))
    data = out.read_bytes()
    # Plus d'un objet Page => plusieurs pages.
    assert data.count(b"/Type /Page") >= 2