"""abc_parser.py — Parsing, filtrage et validation de partitions ABC.

Ce module transforme un texte au format `ABC notation <https://abcnotation.com>`_
en une structure Python exploitable par le moteur de rendu PDF.

Périmètre volontairement restreint :

* Le parseur reconnaît les en-têtes ABC usuels (``X``, ``T``, ``M``, ``L``, ``K``,
  ``Q``, ...) ainsi que le corps de mélodie.
* Les événements de musique sont convertis en :class:`NoteEvent`
  (note ou silence) et :class:`BarEvent` (barre de mesure).
* **Seule la gamme de 8 notes Do4..Do5 est acceptée** (cf. ``config.gamut``).
  Les notes hors gamme sont traitées selon la politique ``config.policy``.

Le parseur n'a aucune dépendance à ReportLab : il est testable indépendamment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Union

from config import NoteConfig, ScoreConfig

# ---------------------------------------------------------------------------
# Constantes musicales
# ---------------------------------------------------------------------------

#: Demi-tons (par rapport au Do) des 7 degrés diatoniques.
_PITCH_CLASS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

#: MIDI de référence : Do4 = 60 et Do5 = 72 (notation scientifique).
_MIDI_C4 = 60
_MIDI_C5 = 72


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ABCParseError(Exception):
    """Erreur de syntaxe ou de validation d'une partition ABC."""


class OutOfRangeError(ABCParseError):
    """Une note est hors de la gamme autorisée et la politique vaut 'error'."""


# ---------------------------------------------------------------------------
# Structures de données
# ---------------------------------------------------------------------------


@dataclass
class NoteEvent:
    """Un événement musical rendu sur la portée (note ou silence)."""

    abc_symbol: str
    is_rest: bool = False
    duration: float = 1.0
    note: Optional[NoteConfig] = None
    midi: Optional[int] = None
    original: str = ""

    @property
    def color(self) -> Optional[str]:
        return self.note.color if self.note else None


@dataclass
class BarEvent:
    """Une barre de mesure ou un symbole de reprise/barre finale."""

    symbol: str


Event = Union[NoteEvent, BarEvent]


@dataclass
class Score:
    """Représentation complète d'une partition ABC prête à être rendue."""

    title: str = ""               # renseigné par le champ T:, sinon "Sans titre"
    composer: str = ""            # champ optionnel (C:)
    meter: str = "4/4"
    default_length: str = "1/8"
    key: str = "C"
    tempo: Optional[str] = None
    events: List[Event] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def notes(self) -> List[NoteEvent]:
        """Retourne uniquement les événements de type note/silence."""
        return [e for e in self.events if isinstance(e, NoteEvent)]

    @property
    def note_count(self) -> int:
        return len(self.notes)


# ---------------------------------------------------------------------------
# Utilitaires internes
# ---------------------------------------------------------------------------

# Un en-tête ABC ressemble à "X:1" en début de ligne.
_HEADER_RE = re.compile(r"^([A-Za-z]):\s*(.*)$")
# Un token de note : altération + lettre + marqueurs d'octave + durée.
_NOTE_TOKEN_RE = re.compile(r"(\^|_|=)?([A-Ga-g])([,']*)(\d+/\d+|/+|\d+)?")
# Durée simple : nombre, ou /, ou /n.
_DUR_RE = re.compile(r"^(?:(\d+)(?:/(\d+))?|/(\d+)?)$")
_BAR_TOKENS = ("|]", "||", "|:", ":|", "::", "[|")


def _parse_length_field(text: str) -> float:
    """Convertit un champ de longueur ABC (``1/8``, ``1/4``...) en fraction."""
    text = text.strip()
    m = _DUR_RE.match(text)
    if not m:
        return 1.0
    num, den, slash_only = m.groups()
    if num is not None:
        numerator = int(num)
        denominator = int(den) if den else 1
        return numerator / denominator
    denominator = int(slash_only) if slash_only else 2
    return 1.0 / denominator


def _letters_to_midi(letter: str, octave_marks: str, accidental: str) -> int:
    """Calcule la hauteur MIDI d'une lettre ABC (avant filtrage de gamme)."""
    base_octave = 5 if letter.islower() else 4
    upper = letter.upper()
    octave = base_octave + octave_marks.count("'") - octave_marks.count(",")
    midi = (octave + 1) * 12 + _PITCH_CLASS[upper]

    if accidental == "^":
        midi += 1
    elif accidental == "_":
        midi -= 1
    return midi


def _gamut_midis(cfg: ScoreConfig) -> List[int]:
    """Retourne les hauteurs MIDI autorisées triées (issues de la config)."""
    midis = []
    for note in cfg.notes.values():
        midis.append((note.octave + 1) * 12 + _PITCH_CLASS[note.abc.upper()])
    return sorted(set(midis))


def _apply_policy(midi: int, policy: str, abc_symbol: str, cfg: ScoreConfig) -> Optional[int]:
    """Applique la politique hors-gamme et retourne un MIDI dans [C4, C5].

    Retourne ``None`` si la note doit être ignorée (politique ``skip``).

    Raises:
        OutOfRangeError: si la politique vaut ``error``.
        ABCParseError: si la politique est inconnue.
    """
    allowed = _gamut_midis(cfg)

    # Repli d'octave : on ramène la hauteur dans la fenêtre C4..C5.
    folded = midi
    while folded < _MIDI_C4:
        folded += 12
    while folded > _MIDI_C5:
        folded -= 12

    if folded in allowed:
        return folded

    # Hauteur chromatique (altération) : on choisit la touche la plus proche.
    original_folded = folded
    nearest = min(allowed, key=lambda a: (abs(a - folded), a))

    if original_folded in allowed:
        return original_folded

    if policy == "transpose":
        return nearest
    if policy == "skip":
        return None
    if policy == "error":
        raise OutOfRangeError(
            f"Note '{abc_symbol}' (MIDI {midi}) hors de la gamme Do4-Do5 et "
            f"non transposable exactement."
        )
    raise ABCParseError(f"Politique hors-gamme inconnue : '{policy}'")


# ---------------------------------------------------------------------------
# Parseur principal
# ---------------------------------------------------------------------------


def parse_abc(text: str, cfg: ScoreConfig) -> Score:
    """Parse un texte ABC et retourne un :class:`Score` filtré sur la gamme.

    Args:
        text: contenu du fichier ABC.
        cfg: configuration validée (gamme + politique de traitement).

    Raises:
        ABCParseError: si aucune note exploitable n'est trouvée ou si la
            politique hors-gamme vaut ``error``.
    """
    score = Score()
    body_lines: List[str] = []
    in_body = False

    for raw_line in text.splitlines():
        line = raw_line.split("%", 1)[0].rstrip()  # retire les commentaires
        if not line.strip():
            continue

        header = _HEADER_RE.match(line)
        if header and not in_body:
            field_letter, value = header.group(1), header.group(2).strip()
            _apply_header(score, field_letter, value)
            if field_letter.upper() == "K":
                in_body = True
            continue

        in_body = True
        body_lines.append(line)

    if not body_lines:
        raise ABCParseError("Aucun corps de mélodie trouvé (champ K: manquant ?).")

    body = " ".join(body_lines)
    # Supprime annotations/accords et décorations pour ne garder que la musique.
    body = re.sub(r'"[^"]*"', " ", body)      # "Am", "texte"
    body = re.sub(r"\{[^}]*\}", " ", body)    # ornements {c}
    body = re.sub(r"![^!]*!", " ", body)      # !fermata!
    body = re.sub(r"\+[^+]*\+", " ", body)

    default_len = _parse_length_field(score.default_length)
    _tokenize_body(score, body, default_len, cfg)

    if score.note_count == 0:
        raise ABCParseError("Aucune note exploitable : vérifiez la partition ABC.")

    if not score.title:
        score.title = "Sans titre"
    return score


def _apply_header(score: Score, letter: str, value: str) -> None:
    """Applique un champ d'en-tête ABC au :class:`Score`."""
    key = letter.upper()
    if key == "T":
        # Un second champ T: (sous-titre) est concaténé.
        score.title = f"{score.title} {value}".strip() if score.title else value
    elif key == "C":
        score.composer = value
    elif key == "M":
        score.meter = value or "4/4"
    elif key == "L":
        score.default_length = value or "1/8"
    elif key == "K":
        score.key = value.split()[0] if value else "C"
    elif key == "Q":
        score.tempo = value


def _tokenize_body(score: Score, body: str, default_len: float, cfg: ScoreConfig) -> None:
    """Découpe le corps ABC en événements (notes, silences, barres)."""
    policy = str(cfg.policy.get("out_of_range", "skip")).lower()
    i = 0
    n = len(body)

    while i < n:
        ch = body[i]

        if ch.isspace():
            i += 1
            continue

        bar = _match_bar(body, i)
        if bar is not None:
            score.events.append(BarEvent(symbol=bar))
            i += len(bar)
            continue

        if ch in "zx":
            match = _NOTE_TOKEN_RE.match(body, i)
            dur = _duration_from_match(match, default_len) if match else default_len
            step = match.end() - i if match else 1
            score.events.append(NoteEvent(abc_symbol=ch, is_rest=True,
                                          duration=dur, original=ch))
            i += step
            continue

        if ch in "XZ":  # silences multi-mesures : traités comme un silence simple
            score.events.append(NoteEvent(abc_symbol=ch, is_rest=True,
                                          duration=default_len, original=ch))
            i += 1
            continue

        match = _NOTE_TOKEN_RE.match(body, i)
        if match:
            acc, letter, marks, dur_tok = match.groups()
            duration = _duration_from_token(dur_tok, default_len)
            midi = _letters_to_midi(letter, marks, acc or "=")
            midi = _apply_policy(midi, policy, match.group(0), cfg)

            if midi is None:
                i = match.end()
                continue  # politique "skip"

            note_cfg = _note_config_for_midi(midi, cfg)
            score.events.append(
                NoteEvent(abc_symbol=letter, duration=duration, note=note_cfg,
                          midi=midi, original=match.group(0))
            )
            i = match.end()
            continue

        if ch == "(":  # tuplets : on ignore le marqueur, les notes suivent
            i += 2 if i + 1 < n and body[i + 1].isdigit() else 1
            continue

        i += 1


def _match_bar(body: str, i: int) -> Optional[str]:
    """Retourne le symbole de barre trouvé à la position ``i``, sinon None."""
    for tok in _BAR_TOKENS:
        if body.startswith(tok, i):
            return tok
    if body[i] == "|":
        return "|"
    if body[i] == ":":
        return ":"
    return None


def _duration_from_match(match: "re.Match[str]", default_len: float) -> float:
    """Durée d'un silence à partir de son token."""
    groups = match.groups()
    return _duration_from_token(groups[3] if len(groups) > 3 else None, default_len)


def _duration_from_token(token: Optional[str], default_len: float) -> float:
    """Convertit un modificateur de durée ABC en fraction de ronde."""
    if not token:
        return default_len
    m = _DUR_RE.match(token)
    if not m:
        return default_len
    num, den, slash_only = m.groups()
    if num is not None:
        numerator = int(num)
        denominator = int(den) if den else 1
        return default_len * numerator / denominator
    denominator = int(slash_only) if slash_only else 2
    return default_len / denominator


def _note_config_for_midi(midi: int, cfg: ScoreConfig) -> NoteConfig:
    """Retrouve la :class:`NoteConfig` correspondant à une hauteur MIDI."""
    for note in cfg.notes.values():
        if (note.octave + 1) * 12 + _PITCH_CLASS[note.abc.upper()] == midi:
            return note
    raise ABCParseError(f"Aucune note de la gamme ne correspond à MIDI {midi}.")


def load_abc_file(path: str, cfg: ScoreConfig) -> Score:
    """Charge un fichier ABC depuis le disque et le parse.

    Raises:
        ABCParseError: fichier introuvable ou illisible.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise ABCParseError(f"Impossible de lire le fichier ABC '{path}' : {exc}") from exc
    return parse_abc(text, cfg)