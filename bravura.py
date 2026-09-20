"""bravura.py — Accès aux glyphes de la fonte musicale Bravura.

Bravura (licence SIL Open Font License) est une fonte musicale « SMuFL » qui
fournit des glyphes d'une qualité typographique professionnelle : clé de sol,
têtes de note, silences, crochets (hampes), altérations, points, etc.

ReportLab ne sait pas embarquer des contours PostScript (CFF, format .otf).
Nous livrons donc dans ``assets/`` une version ``Bravura.ttf`` (contours
TrueType) obtenue par conversion unique via ``fontTools``. Ce module gère
l'enregistrement de la fonte auprès de ReportLab et expose les points de code
SMuFL utiles.

Référence SMuFL : https://w3c.github.io/smufl/
"""

from __future__ import annotations

import os
from functools import lru_cache

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

#: Nom logique utilisé pour référencer la fonte dans ReportLab.
BRAVURA_NAME = "Bravura"

#: Unité de base SMuFL : 1 espace de portée = 250 unités d'em (upem = 1000).
STAFF_SPACE_UNITS = 250.0

#: Chemin par défaut de la fonte (à côté de ce module).
_DEFAULT_FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "assets", "Bravura.ttf")

# ---------------------------------------------------------------------------
# Points de code SMuFL des glyphes utilisés
# ---------------------------------------------------------------------------
GLYPHS = {
    "g_clef":         0xE050,  # clé de sol
    "notehead_black": 0xE0A4,  # tête de note noire (noire, croche, ...)
    "notehead_half":  0xE0A3,  # tête de note blanche (blanche)
    "notehead_whole": 0xE0A2,  # tête de note ronde
    "rest_whole":     0xE4E3,
    "rest_half":      0xE4E4,
    "rest_quarter":   0xE4E5,
    "rest_8th":       0xE4E6,
    "flag_8th_up":    0xE240,  # crochet de croche (hampe vers le haut)
    "flag_8th_down":  0xE241,  # crochet de croche (hampe vers le bas)
    "dot":            0xE1E7,  # point de prolongation
}


@lru_cache(maxsize=1)
def register_font(font_path: str | None = None) -> str:
    """Enregistre la fonte Bravura auprès de ReportLab (idempotent).

    Args:
        font_path: chemin explicite vers ``Bravura.ttf``. Si ``None``, on
            utilise ``assets/Bravura.ttf``.

    Returns:
        Le nom logique de la fonte enregistrée.

    Raises:
        FileNotFoundError: si le fichier de fonte est introuvable.
    """
    path = font_path or _DEFAULT_FONT
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Fonte musicale introuvable : {path}. "
            "Lancez `python tools/build_font.py` pour la générer depuis l'OTF."
        )
    if BRAVURA_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(BRAVURA_NAME, path))
    return BRAVURA_NAME


def glyph(ch: str) -> str:
    """Retourne le caractère Unicode correspondant au glyphe logique ``ch``.

    >>> glyph("g_clef") == "\\uE050"
    True
    """
    if ch not in GLYPHS:
        raise KeyError(f"Glyphe inconnu : '{ch}'. Disponibles : {sorted(GLYPHS)}")
    return chr(GLYPHS[ch])