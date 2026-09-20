"""build_font.py — Génère ``assets/Bravura.ttf`` depuis ``assets/Bravura.otf``.

ReportLab ne peut pas embarquer des contours PostScript (fonte CFF/OTF). Ce
script convertit la fonte musicale Bravura (SMuFL, licence OFL) en TrueType à
l'aide de ``fontTools`` (module ``cu2qu``), afin que ``bravura.py`` puisse
l'enregistrer auprès de ReportLab.

À exécuter une seule fois après clonage, ou après mise à jour de la fonte OTF :

    python tools/build_font.py

Le fichier ``assets/Bravura.ttf`` ainsi produit est versionné : la conversion
n'est donc pas nécessaire pour un simple usage de l'application.
"""

from __future__ import annotations

import os
import sys

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._g_l_y_f import Glyph, table__g_l_y_f

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ASSETS = os.path.join(_ROOT, "assets")
_SRC = os.path.join(_ASSETS, "Bravura.otf")
_DST = os.path.join(_ASSETS, "Bravura.ttf")


def otf_to_ttf(in_path: str, out_path: str, max_err: float = 1.0) -> None:
    """Convertit une fonte OTF (contours CFF) en TTF (contours TrueType).

    Args:
        in_path: chemin de la fonte source (.otf).
        out_path: chemin de la fonte destination (.ttf).
        max_err: erreur maximale (en unités d'em) tolérée par l'approximation
            quadratique.
    """
    font = TTFont(in_path)
    glyph_set = font.getGlyphSet()
    order = font.getGlyphOrder()

    glyf = table__g_l_y_f()
    glyf.glyphOrder = order
    glyf.glyphs = {}
    for name in order:
        pen = TTGlyphPen(glyph_set)
        try:
            glyph_set[name].draw(Cu2QuPen(pen, max_err=max_err, reverse_direction=True))
            glyf[name] = pen.glyph()
        except Exception:
            glyf[name] = Glyph()

    font["glyf"] = glyf
    font["loca"] = newTable("loca")

    for tag in ("CFF ", "VORG", "CFF2"):
        if tag in font:
            del font[tag]

    maxp = font["maxp"]
    maxp.tableVersion = 0x00010000
    for attr in ("maxTwilightPoints", "maxStorage", "maxFunctionDefs",
                 "maxInstructionDefs", "maxStackElements", "maxSizeOfInstructions",
                 "maxComponentElements"):
        setattr(maxp, attr, 0)
    maxp.maxZones = 1

    if "post" in font:
        font["post"].formatType = 3.0  # pas de noms de glyphes (évite extraNames)

    font.sfntVersion = "\x00\x01\x00\x00"  # marque la fonte comme TrueType
    font.save(out_path)


def main() -> int:
    """Point d'entrée du script de génération de fonte."""
    if not os.path.isfile(_SRC):
        print(f"[ERREUR] Fonte source introuvable : {_SRC}", file=sys.stderr)
        return 1
    print(f"[font] Conversion {_SRC} -> {_DST} ...")
    otf_to_ttf(_SRC, _DST)
    print("[font] Terminé.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())