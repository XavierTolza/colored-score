"""config.py — Chargement, validation et accès typé à la configuration.

Ce module fait le pont entre le fichier ``config.yaml`` (source de vérité,
éditable par l'utilisateur) et le reste de l'application. Il expose :

* :class:`NoteConfig`   : une note de la gamme + sa couleur.
* :class:`ScoreConfig`  : objet d'accès haut niveau (notes, layout, couleurs...).

Le chargement est volontairement défensif : toute incohérence (couleur invalide,
note manquante, format de page inconnu...) lève une :class:`ConfigError`
explicite plutôt que de produire un PDF silencieusement erroné.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

import yaml

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    """Erreur de configuration (fichier absent, valeur invalide, ...)."""


# ---------------------------------------------------------------------------
# Structures de données
# ---------------------------------------------------------------------------

#: Ordre des 8 touches du clavier Baby Einstein / Hape (de gauche à droite).
DEFAULT_KEY_ORDER: List[str] = ["C", "D", "E", "F", "G", "A", "B", "c"]

def _is_hex_color(value: str) -> bool:
    """Retourne True si ``value`` est une couleur hexadécimale ``#RRGGBB``."""
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        return False
    try:
        int(value[1:], 16)
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class NoteConfig:
    """Description d'une note de la gamme et de sa couleur."""

    abc: str          # symbole ABC (C, D, ..., c)
    name: str         # nom français (Do, Ré, ...)
    octave: int       # octave (4 ou 5)
    order: int        # position physique sur le clavier (1..8)
    color: str        # couleur hexadécimale #RRGGBB
    label_en: str = ""  # libellé scientifique (C4, D4, ...)

    @property
    def rgb(self) -> tuple[float, float, float]:
        """Retourne la couleur sous forme de triplet RGB normalisé (0..1)."""
        r = int(self.color[1:3], 16) / 255.0
        g = int(self.color[3:5], 16) / 255.0
        b = int(self.color[5:7], 16) / 255.0
        return (r, g, b)


@dataclass
class ScoreConfig:
    """Vue haut niveau et typée de la configuration complète."""

    raw: Dict[str, Any]
    notes: Dict[str, NoteConfig]
    base_dir: str = "."

    # -- Accès raccourcis ---------------------------------------------------

    @property
    def colors(self) -> Dict[str, str]:
        return self.raw.get("colors", {})

    @property
    def layout(self) -> Dict[str, Any]:
        return self.raw.get("layout", {})

    @property
    def policy(self) -> Dict[str, Any]:
        return self.raw.get("policy", {})

    @property
    def output(self) -> Dict[str, Any]:
        return self.raw.get("output", {})

    @property
    def gamut(self) -> Dict[str, Any]:
        return self.raw.get("gamut", {})

    # -- Helpers métier -----------------------------------------------------

    def note_by_abc(self, abc: str) -> NoteConfig:
        """Retourne la configuration d'une note à partir de son symbole ABC.

        Les altérations accidentelles (``^``, ``_``, ``=``) sont retirées avant
        la recherche : la gamme supportée est diatonique (pas de dièses/bémols).
        """
        key = abc.lstrip("^_=")
        if key not in self.notes:
            raise ConfigError(
                f"Note ABC '{abc}' inconnue. Notes supportées : "
                f"{', '.join(sorted(self.notes))}"
            )
        return self.notes[key]

    def ordered_notes(self) -> List[NoteConfig]:
        """Retourne les 8 notes triées par position physique sur le clavier."""
        return sorted(self.notes.values(), key=lambda n: n.order)

    def page_size_name(self) -> str:
        return str(self.layout.get("page_size", "A4")).upper()

    def orientation(self) -> str:
        return str(self.layout.get("orientation", "portrait")).lower()


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------


def load_config(path: str | None = None) -> ScoreConfig:
    """Charge, valide et retourne la configuration.

    Args:
        path: chemin vers ``config.yaml``. Par défaut, on cherche ``config.yaml``
            à côté de ce module.

    Raises:
        ConfigError: fichier introuvable, YAML invalide ou données incohérentes.
    """
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")

    if not os.path.isfile(path):
        raise ConfigError(f"Fichier de configuration introuvable : {path}")

    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    except yaml.YAMLError as exc:  # pragma: no cover - dépend du fichier fourni
        raise ConfigError(f"YAML invalide dans {path} : {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"Le fichier de configuration {path} doit être un mapping YAML.")

    notes = _parse_notes(raw.get("notes"))
    _validate_layout(raw)
    _validate_colors(raw)

    return ScoreConfig(raw=raw, notes=notes, base_dir=os.path.dirname(os.path.abspath(path)))


def _parse_notes(section: Any) -> Dict[str, NoteConfig]:
    """Valide la section ``notes`` et construit le mapping ABC -> NoteConfig."""
    if not isinstance(section, dict) or not section:
        raise ConfigError("La section 'notes' est absente ou vide dans config.yaml.")

    notes: Dict[str, NoteConfig] = {}
    for abc, data in section.items():
        if not isinstance(data, dict):
            raise ConfigError(f"Note '{abc}' : la définition doit être un mapping.")

        color = data.get("color", "")
        if not _is_hex_color(color):
            raise ConfigError(
                f"Note '{abc}' : couleur '{color}' invalide (format attendu #RRGGBB)."
            )

        try:
            note = NoteConfig(
                abc=str(abc),
                name=str(data.get("name", abc)),
                octave=int(data.get("octave", 4)),
                order=int(data.get("order", 0)),
                color=color.upper(),
                label_en=str(data.get("label_en", "")),
            )
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"Note '{abc}' : champ numérique invalide ({exc}).") from exc

        notes[str(abc)] = note

    missing = [k for k in DEFAULT_KEY_ORDER if k not in notes]
    if missing:
        raise ConfigError(
            f"Notes manquantes dans la gamme (attendu {DEFAULT_KEY_ORDER}) : {missing}"
        )
    return notes


def _validate_layout(raw: Dict[str, Any]) -> None:
    """Vérifie la cohérence minimale de la mise en page."""
    layout = raw.get("layout")
    if not isinstance(layout, dict):
        raise ConfigError("La section 'layout' est absente ou invalide.")

    valid_sizes = {"A0", "A1", "A2", "A3", "A4", "A5", "A6", "LETTER", "LEGAL", "ELEVENSEVENTEEN"}
    size = str(layout.get("page_size", "A4")).upper()
    if size not in valid_sizes:
        raise ConfigError(
            f"page_size '{size}' non supporté. Valeurs possibles : {sorted(valid_sizes)}"
        )

    orientation = str(layout.get("orientation", "portrait")).lower()
    if orientation not in {"portrait", "landscape"}:
        raise ConfigError("orientation doit être 'portrait' ou 'landscape'.")

    staff = layout.get("staff", {})
    if float(staff.get("space", 0)) <= 0:
        raise ConfigError("layout.staff.space doit être > 0 (mm).")


def _validate_colors(raw: Dict[str, Any]) -> None:
    """Vérifie que les couleurs générales sont au bon format."""
    colors = raw.get("colors", {})
    for key, value in colors.items():
        if not _is_hex_color(str(value)):
            raise ConfigError(f"colors.{key} = '{value}' invalide (format #RRGGBB).")