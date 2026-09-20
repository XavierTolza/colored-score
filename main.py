"""main.py — Point d'entrée de l'application Colored-Score.

Transforme une partition au format ABC en un PDF visuel coloré, où chaque note
adopte la couleur de la touche correspondante du clavier Baby Einstein / Hape.

Exemples d'utilisation :

    # Générer le PDF d'un fichier ABC
    python main.py samples/frere_jacques.abc

    # Spécifier le PDF de sortie et la configuration
    python main.py samples/ode_a_la_joie.abc -o output/ode.pdf --config config.yaml

    # Générer tous les exemples
    python main.py --all
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from typing import List, Optional

from abc_parser import ABCParseError, load_abc_file, parse_abc
from config import ConfigError, ScoreConfig, load_config
from pdf_generator import PDFGenerationError, PDFGenerator


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------


def slugify(text: str) -> str:
    """Convertit un titre en nom de fichier sûr (sans accents ni espaces)."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = re.sub(r"[^\w\s-]", "", ascii_text).strip().lower()
    return re.sub(r"[\s_-]+", "_", ascii_text) or "score"


def resolve_output_path(cfg: ScoreConfig, title: str, explicit: Optional[str]) -> str:
    """Détermine le chemin de sortie du PDF."""
    if explicit:
        return explicit
    out_dir = cfg.output.get("directory", "output")
    pattern = cfg.output.get("filename_pattern", "{title_slug}.pdf")
    filename = pattern.format(title_slug=slugify(title))
    if not os.path.isabs(out_dir):
        out_dir = os.path.join(cfg.base_dir, out_dir)
    return os.path.join(out_dir, filename)


def generate_pdf(abc_path: str, cfg: ScoreConfig, output: Optional[str] = None,
                 font_path: Optional[str] = None) -> str:
    """Pipeline complet : lecture ABC -> parsing -> rendu PDF.

    Returns:
        Le chemin du PDF généré.
    """
    score = load_abc_file(abc_path, cfg)
    out_path = resolve_output_path(cfg, score.title, output)

    generator = PDFGenerator(cfg, font_path=font_path)
    return generator.generate(score, out_path)


def _iter_abc_files(directory: str) -> List[str]:
    """Liste les fichiers .abc d'un répertoire (triés)."""
    if not os.path.isdir(directory):
        return []
    return sorted(os.path.join(directory, f)
                  for f in os.listdir(directory) if f.lower().endswith(".abc"))


# ---------------------------------------------------------------------------
# Interface en ligne de commande
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Construit le parseur d'arguments CLI."""
    parser = argparse.ArgumentParser(
        prog="colored-score",
        description="Génère des partitions PDF colorées à partir de fichiers ABC.",
    )
    parser.add_argument("abc", nargs="?", help="Fichier de partition ABC (.abc).")
    parser.add_argument("-o", "--output", help="Chemin du PDF de sortie.")
    parser.add_argument("--config", default=None, help="Fichier de configuration YAML.")
    parser.add_argument("--font", default=None, help="Chemin vers Bravura.ttf.")
    parser.add_argument("--all", action="store_true",
                        help="Génère le PDF de tous les fichiers du dossier samples/.")
    parser.add_argument("--samples-dir", default=None,
                        help="Dossier des fichiers ABC (avec --all).")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Point d'entrée principal. Retourne un code de sortie."""
    args = build_parser().parse_args(argv)

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"[ERREUR config] {exc}", file=sys.stderr)
        return 2

    font_path = args.font
    if font_path is None:
        font_path = os.path.join(cfg.base_dir, "assets", "Bravura.ttf")

    jobs: List[str] = []
    if args.all:
        samples_dir = args.samples_dir or os.path.join(cfg.base_dir, "samples")
        jobs = _iter_abc_files(samples_dir)
        if not jobs:
            print(f"[ERREUR] Aucun fichier .abc dans {samples_dir}", file=sys.stderr)
            return 1
    elif args.abc:
        jobs = [args.abc]
    else:
        build_parser().print_help()
        return 1

    failures = 0
    for abc_path in jobs:
        try:
            out = generate_pdf(abc_path, cfg, args.output if len(jobs) == 1 else None,
                               font_path)
            print(f"[OK]   {abc_path}  ->  {out}")
        except (ABCParseError, PDFGenerationError, ConfigError) as exc:
            print(f"[FAIL] {abc_path} : {exc}", file=sys.stderr)
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())