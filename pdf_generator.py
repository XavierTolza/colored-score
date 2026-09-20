"""pdf_generator.py — Moteur de rendu graphique et génération du PDF.

Ce module dessine une portée classique (clé de sol) sur un canvas ReportLab et
colore chaque note selon la correspondance stricte définie dans ``config.yaml``.

Choix techniques :

* La portée, les hampes, crochets et barres sont dessinés en primitives
  vectorielles (lignes / rectangles) : rendu net à l'impression.
* Les glyphes musicaux (clé de sol, têtes de note, silences) proviennent de la
  fonte **Bravura** (SMuFL), embarquée dans ``assets/`` : qualité typographique.
* Toute la géométrie (format de page, marges, dimensions) est lue depuis la
  configuration : rien n'est codé « en dur ».

Gamme supportée : Do4..Do5 (8 touches du clavier). Les hauteurs sont converties
en « position sur la portée » où l'unité = un demi-interligne.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, A4, A5, A6, LEGAL, LETTER, landscape, portrait
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

import bravura
from abc_parser import BarEvent, NoteEvent, Score
from config import NoteConfig, ScoreConfig

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

#: Formats de page ReportLab reconnus.
_PAGE_SIZES = {
    "A3": A3, "A4": A4, "A5": A5, "A6": A6,
    "LETTER": LETTER, "LEGAL": LEGAL,
}

#: Index diatonique de la ligne inférieure de la portée en clé de sol (Mi4).
_BOTTOM_LINE_INDEX = 4 * 7 + 2  # E4

#: Haut de portée (ligne supérieure = Fa5) : index + 4.
#: Une position de portée vaut 0.5 interligne par degré diatonique.

_STEPS = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PDFGenerationError(Exception):
    """Erreur durant la génération du PDF."""


# ---------------------------------------------------------------------------
# Structures internes
# ---------------------------------------------------------------------------


@dataclass
class _RenderItem:
    """Élément prêt à être dessiné, avec sa position horizontale (mm)."""

    event: object          # NoteEvent ou BarEvent
    x: float               # position horizontale depuis la marge gauche (mm)
    width: float           # largeur consommée (mm)


# ---------------------------------------------------------------------------
# Générateur
# ---------------------------------------------------------------------------


class PDFGenerator:
    """Génère un PDF coloré à partir d'un :class:`~abc_parser.Score`.

    Args:
        cfg: configuration validée.
        font_path: chemin optionnel vers ``Bravura.ttf``.
    """

    def __init__(self, cfg: ScoreConfig, font_path: Optional[str] = None) -> None:
        self.cfg = cfg
        self.layout = cfg.layout
        self.notes_style = self.layout.get("notes_style", {})
        self.staff_cfg = self.layout.get("staff", {})
        self.general_colors = cfg.colors
        self.font_path = font_path

        # Dimension de page (points).
        size_name = cfg.page_size_name()
        if size_name not in _PAGE_SIZES:
            raise PDFGenerationError(f"Format de page non supporté : {size_name}")
        self.page_w, self.page_h = _PAGE_SIZES[size_name]
        if cfg.orientation() == "landscape":
            self.page_w, self.page_h = landscape((self.page_w, self.page_h))
        else:
            self.page_w, self.page_h = portrait((self.page_w, self.page_h))

        # Marges en points.
        margins = self.layout.get("margins", {})
        self.margin_left = float(margins.get("left", 15)) * mm
        self.margin_right = float(margins.get("right", 15)) * mm
        self.margin_top = float(margins.get("top", 20)) * mm
        self.margin_bottom = float(margins.get("bottom", 20)) * mm

        # Interligne de portée (points).
        self.staff_space = float(self.staff_cfg.get("space", 3.2)) * mm

        # Zone utile.
        self.content_w = self.page_w - self.margin_left - self.margin_right

        self._font_name = bravura.register_font(font_path)
        # Échelle : 1 unité SMuFL = `unit` points.
        self.unit = self.staff_space / bravura.STAFF_SPACE_UNITS
        self.music_font_size = 1000.0 * self.unit  # upem = 1000

        self.c = rl_canvas.Canvas("", pagesize=(self.page_w, self.page_h))  # placeholder

    # ------------------------------------------------------------------
    # Conversions de coordonnées
    # ------------------------------------------------------------------
    def _Y(self, mm_from_top: float) -> float:
        """Convertit une distance depuis le haut de page (mm) en Y ReportLab."""
        return self.page_h - mm_from_top * mm

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------
    def generate(self, score: Score, output_path: str) -> str:
        """Génère le PDF et retourne son chemin.

        Args:
            score: partition parsée.
            output_path: chemin du fichier PDF à écrire.

        Raises:
            PDFGenerationError: en cas d'échec d'écriture.
        """
        directory = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(directory, exist_ok=True)

        self.c = rl_canvas.Canvas(output_path, pagesize=(self.page_w, self.page_h))
        self.c.setTitle(score.title)

        self._draw_title(score)

        systems = self._build_systems(score)
        cursor = self._content_start_mm(score)
        # En coordonnées ReportLab, Y croît vers le haut : la limite basse utile
        # est simplement la marge basse (exprimée en points).
        bottom_limit = self.margin_bottom

        for system in systems:
            # Saut de page si le système descend sous la marge inférieure.
            if self._Y(cursor + self._system_height_mm()) < bottom_limit:
                self._draw_legend(cursor + float(
                    self.layout.get("legend", {}).get("spacing_before", 12)))
                self.c.showPage()
                cursor = self.margin_top / mm + 6.0

            self._draw_system(system, cursor)
            cursor += self._system_height_mm()

        self._draw_legend(cursor + float(
            self.layout.get("legend", {}).get("spacing_before", 12)))

        try:
            self.c.save()
        except OSError as exc:  # pragma: no cover - dépend du disque
            raise PDFGenerationError(f"Impossible d'écrire le PDF : {exc}") from exc
        return output_path

    # ------------------------------------------------------------------
    # Titre / en-tête
    # ------------------------------------------------------------------
    def _content_start_mm(self, score: Score) -> float:
        """Retourne l'abscisse (mm depuis le haut) où commence la 1ère portée."""
        title_cfg = self.layout.get("title", {})
        sub_cfg = self.layout.get("subtitle", {})
        top_mm = self.margin_top / mm
        top_mm += float(title_cfg.get("font_size", 22)) * 0.42
        top_mm += float(title_cfg.get("spacing_after", 4))
        if score.composer or score.key:
            top_mm += float(sub_cfg.get("font_size", 10)) * 0.42
            top_mm += float(sub_cfg.get("spacing_after", 10))
        top_mm += 6.0  # petit dégagement avant la portée
        return top_mm

    def _draw_title(self, score: Score) -> None:
        """Dessine le titre et le sous-titre (compositeur / tonalité)."""
        text_color = colors.HexColor(self.general_colors.get("text", "#1A1A1A"))
        title_cfg = self.layout.get("title", {})
        sub_cfg = self.layout.get("subtitle", {})

        self.c.setFillColor(text_color)
        self.c.setFont(title_cfg.get("font_name", "Helvetica-Bold"),
                       float(title_cfg.get("font_size", 22)))
        title_y = self._Y(self.margin_top / mm + float(title_cfg.get("font_size", 22)) * 0.42)
        self.c.drawCentredString(self.page_w / 2, title_y, score.title)

        parts = []
        if score.composer:
            parts.append(score.composer)
        subtitle = " · ".join(parts)
        if subtitle:
            self.c.setFont(sub_cfg.get("font_name", "Helvetica-Oblique"),
                           float(sub_cfg.get("font_size", 10)))
            sub_y = title_y - float(title_cfg.get("font_size", 22)) * 0.42 \
                - float(title_cfg.get("spacing_after", 4)) * mm
            self.c.drawCentredString(self.page_w / 2, sub_y, subtitle)

    # ------------------------------------------------------------------
    # Construction des systèmes (lignes de portée)
    # ------------------------------------------------------------------
    def _system_height_mm(self) -> float:
        """Hauteur d'un système (mm) : portée + libellés + dégagement."""
        staff_h = 4 * (self.staff_space / mm)
        label_extra = float(self.notes_style.get("label_offset", 9)) + 4 \
            if self.notes_style.get("show_labels", True) else 4
        gap = float(self.staff_cfg.get("system_gap", 20))
        return staff_h + label_extra + gap * 0.35

    def _build_systems(self, score: Score) -> List[List[_RenderItem]]:
        """Répartit les événements en systèmes selon la largeur disponible."""
        spacing = float(self.notes_style.get("spacing", 9))
        ledger_len = float(self.notes_style.get("ledger_length", 2.6))

        left_pad = float(self.staff_cfg.get("left_padding", 12))
        right_pad = float(self.staff_cfg.get("right_padding", 6))
        usable = self.content_w / mm

        systems: List[List[_RenderItem]] = []
        current: List[_RenderItem] = []
        x = left_pad

        for event in score.events:
            if isinstance(event, BarEvent):
                item_w = 2.0
            else:
                item_w = spacing

            # Nouveau système si l'élément ne rentre plus.
            if current and (x + item_w) > (usable - right_pad):
                systems.append(current)
                current = []
                x = left_pad

            current.append(_RenderItem(event=event, x=x, width=item_w))
            x += item_w

        if current:
            systems.append(current)
        return systems

    # ------------------------------------------------------------------
    # Dessin d'un système
    # ------------------------------------------------------------------
    def _draw_system(self, items: List[_RenderItem], top_mm: float) -> None:
        """Dessine une portée complète à partir de ``top_mm`` (depuis le haut)."""
        staff = self.staff_cfg
        space_mm = self.staff_space / mm

        # Y (mm depuis le haut) de chaque ligne : 0 = ligne supérieure.
        def line_mm(k: int) -> float:
            return top_mm + k * space_mm

        bot_line = 4  # ligne inférieure

        # --- Lignes de la portée -------------------------------------------
        self.c.setStrokeColor(colors.HexColor(self.general_colors.get("staff_lines", "#333")))
        self.c.setLineWidth(float(staff.get("line_width", 0.8)))
        left_pad = float(staff.get("left_padding", 12))
        right_pad = float(staff.get("right_padding", 6))
        x_start = self.margin_left + 4 * mm
        x_end = self.page_w - self.margin_right - right_pad * mm
        for k in range(5):
            y = self._Y(line_mm(k))
            self.c.line(x_start, y, x_end, y)

        # --- Clé de sol -----------------------------------------------------
        # En SMuFL, l'origine du glyphe est posée sur la ligne de Sol (2e depuis
        # le bas = index 1). On aligne donc la baseline sur cette ligne.
        g_line_y = self._Y(line_mm(bot_line - 1))
        clef_x = self.margin_left + 3.5 * mm
        self.c.setFont(self._font_name, self.music_font_size)
        self.c.setFillColor(colors.black)
        self.c.drawString(clef_x, g_line_y, bravura.glyph("g_clef"))

        # --- Événements -----------------------------------------------------
        for item in items:
            x_pt = self.margin_left + item.x * mm
            if isinstance(item.event, BarEvent):
                self._draw_barline(item.event, x_pt, top_mm, space_mm)
            else:
                self._draw_note(item.event, x_pt, top_mm, space_mm)

    # ------------------------------------------------------------------
    # Position sur la portée
    # ------------------------------------------------------------------
    @staticmethod
    def _staff_position(note: NoteConfig) -> float:
        """Position sur la portée en unités d'interligne.

        Retourne 0.0 pour la ligne inférieure (Mi4). Chaque degré diatonique
        vaut 0.5. Ex : Do4 -> -1.0 (une portée sous la ligne inférieure),
        Do5 -> 2.5 (3e interligne).
        """
        index = note.octave * 7 + _STEPS[note.abc.upper()]
        return (index - _BOTTOM_LINE_INDEX) / 2.0

    def _position_mm(self, pos: float, top_mm: float, space_mm: float) -> float:
        """Y (mm depuis le haut) d'une position de portée."""
        # pos=0 -> ligne inférieure (index 4).
        return top_mm + (4 - pos) * space_mm

    # ------------------------------------------------------------------
    # Dessin des éléments
    # ------------------------------------------------------------------
    def _draw_barline(self, event: BarEvent, x_pt: float, top_mm: float, space_mm: float) -> None:
        """Dessine une barre de mesure."""
        self.c.setStrokeColor(colors.HexColor(self.general_colors.get("rhythm", "#000")))
        self.c.setLineWidth(float(self.notes_style.get("stem_width", 0.9)))
        y_top = self._Y(top_mm)
        y_bot = self._Y(top_mm + 4 * space_mm)
        self.c.line(x_pt, y_bot, x_pt, y_top)
        if event.symbol in ("|]", "||", ":|", "[|"):
            self.c.line(x_pt + 1.2 * mm, y_bot, x_pt + 1.2 * mm, y_top)

    def _draw_note(self, event: NoteEvent, x_pt: float, top_mm: float, space_mm: float) -> None:
        """Dessine une note (ou un silence) colorée."""
        if event.is_rest:
            self._draw_rest(event, x_pt, top_mm, space_mm)
            return

        note = event.note
        assert note is not None
        color = colors.HexColor(note.color)
        rhythm_color = colors.HexColor(self.general_colors.get("rhythm", "#000"))

        pos = self._staff_position(note)
        y_note_mm = self._position_mm(pos, top_mm, space_mm)
        y_note_pt = self._Y(y_note_mm)

        # --- Lignes supplémentaires (ledger) -------------------------------
        self._draw_ledger_lines(pos, x_pt, top_mm, space_mm)

        # --- Tête de note ---------------------------------------------------
        duration = event.duration
        if duration >= 0.75:
            head = bravura.glyph("notehead_whole")
            head_w_units = 422.0
            draw_stem = False
        elif duration >= 0.375:
            head = bravura.glyph("notehead_half")
            head_w_units = 295.0
            draw_stem = True
        else:
            head = bravura.glyph("notehead_black")
            head_w_units = 295.0
            draw_stem = True

        self.c.setFont(self._font_name, self.music_font_size)
        self.c.setFillColor(color)
        head_x = x_pt - (head_w_units / 2.0) * self.unit
        self.c.drawString(head_x, y_note_pt, head)

        # --- Hampe + crochet -------------------------------------------------
        if draw_stem and duration < 0.75:
            self._draw_stem_and_flag(pos, x_pt, y_note_pt, duration,
                                     head_w_units, color, rhythm_color)

        # --- Point de prolongation ------------------------------------------
        if self._has_dot(event.duration):
            self.c.setFillColor(color)
            self.c.drawString(x_pt + head_w_units * self.unit,
                              y_note_pt, bravura.glyph("dot"))

        # --- Libellé (Do, Ré, ...) ------------------------------------------
        if self.notes_style.get("show_labels", True):
            self._draw_label(note, x_pt, top_mm, space_mm)

    def _draw_stem_and_flag(self, pos: float, x_pt: float, y_note_pt: float,
                            duration: float, head_w_units: float, color, rhythm_color) -> None:
        """Dessine la hampe (et le crochet d'une croche)."""
        stem_len_mm = float(self.notes_style.get("stem_length", 3.4))
        stem_len_pt = stem_len_mm * (self.staff_space / 2.0)
        stem_w = float(self.notes_style.get("stem_width", 0.9))

        # Hampe vers le haut si la note est sous la ligne médiane, sinon bas.
        up = pos < 2.0
        head_half_w = (head_w_units / 2.0) * self.unit

        if up:
            x_stem = x_pt + head_half_w - stem_w * 0.5
            y_from = y_note_pt
            y_to = y_note_pt + stem_len_pt
        else:
            x_stem = x_pt - head_half_w + stem_w * 0.5
            y_from = y_note_pt
            y_to = y_note_pt - stem_len_pt

        self.c.setStrokeColor(color)
        self.c.setLineWidth(stem_w)
        self.c.line(x_stem, y_from, x_stem, y_to)

        # Crochet pour les croches (durée <= 1/8).
        if duration <= 0.1875:
            flag = bravura.glyph("flag_8th_up" if up else "flag_8th_down")
            self.c.setFont(self._font_name, self.music_font_size)
            self.c.setFillColor(color)
            self.c.drawString(x_stem - (10.0 * self.unit if up else 0.0), y_to, flag)

    def _draw_ledger_lines(self, pos: float, x_pt: float, top_mm: float, space_mm: float) -> None:
        """Dessine les lignes supplémentaires nécessaires à une note.

        Les lignes de la portée occupent les positions entières 0..4. Une note
        hors de cet intervalle requiert une ou plusieurs lignes supplémentaires,
        placées aux positions entières paires par rapport aux extrémités.
        """
        ledger_len = float(self.notes_style.get("ledger_length", 2.6)) * mm
        ledgers: List[float] = []
        if pos < 0:
            v = -1
            while v >= pos - 1e-9:
                ledgers.append(float(v))
                v -= 1
        elif pos > 4:
            v = 5
            while v <= pos + 1e-9:
                ledgers.append(float(v))
                v += 1

        if not ledgers:
            return

        self.c.setStrokeColor(colors.HexColor(self.general_colors.get("staff_lines", "#333")))
        self.c.setLineWidth(float(self.staff_cfg.get("line_width", 0.8)))
        for lp in ledgers:
            y = self._Y(self._position_mm(lp, top_mm, space_mm))
            self.c.line(x_pt - ledger_len / 2, y, x_pt + ledger_len / 2, y)

    def _draw_rest(self, event: NoteEvent, x_pt: float, top_mm: float, space_mm: float) -> None:
        """Dessine un silence centré sur la portée."""
        color = colors.HexColor(self.general_colors.get("rhythm", "#000"))
        mid_pos = 2.0  # milieu de la portée
        y = self._Y(self._position_mm(mid_pos, top_mm, space_mm))
        if event.duration >= 0.75:
            glyph = bravura.glyph("rest_whole")
        elif event.duration >= 0.375:
            glyph = bravura.glyph("rest_half")
        elif event.duration >= 0.1875:
            glyph = bravura.glyph("rest_quarter")
        else:
            glyph = bravura.glyph("rest_8th")
        self.c.setFont(self._font_name, self.music_font_size)
        self.c.setFillColor(color)
        self.c.drawString(x_pt - 130 * self.unit, y, glyph)

    @staticmethod
    def _has_dot(duration: float) -> bool:
        """Heuristique : une durée pointée vaut 1.5x une durée simple."""
        simple = {1.0: 1.5, 0.5: 0.75, 0.25: 0.375, 0.125: 0.1875}
        for base, dotted in simple.items():
            if abs(duration - dotted) < 1e-6:
                return True
        return False

    def _draw_label(self, note: NoteConfig, x_pt: float, top_mm: float, space_mm: float) -> None:
        """Dessine le nom français de la note sous la portée."""
        offset = float(self.notes_style.get("label_offset", 9))
        y = self._Y(top_mm + 4 * space_mm + offset)
        self.c.setFont(self.notes_style.get("label_font_name", "Helvetica-Bold"),
                       float(self.notes_style.get("label_font_size", 8)))
        self.c.setFillColor(colors.HexColor(note.color))
        self.c.drawCentredString(x_pt, y, note.name)

    # ------------------------------------------------------------------
    # Légende
    # ------------------------------------------------------------------
    def _draw_legend(self, top_mm: float) -> None:
        """Dessine le clavier de légende (8 touches colorées + libellés)."""
        legend = self.layout.get("legend", {})
        if not legend.get("enabled", True):
            return

        key_w = float(legend.get("key_width", 12)) * mm
        key_h = float(legend.get("key_height", 18)) * mm
        gap = float(legend.get("key_gap", 1.4)) * mm
        notes = self.cfg.ordered_notes()

        total_w = len(notes) * key_w + (len(notes) - 1) * gap
        x = (self.page_w - total_w) / 2.0
        y_top = self._Y(top_mm)

        # Titre de la légende.
        self.c.setFillColor(colors.HexColor(self.general_colors.get("text", "#000")))
        self.c.setFont("Helvetica-Bold", float(legend.get("title_font_size", 11)))
        self.c.drawCentredString(self.page_w / 2,
                                 y_top + 6 * mm, legend.get("title", "Légende"))

        key_top = y_top - key_h
        for note in notes:
            self.c.setFillColor(colors.HexColor(note.color))
            self.c.setStrokeColor(colors.HexColor(self.general_colors.get("note_outline", "#1A1A1A")))
            self.c.setLineWidth(0.8)
            self.c.roundRect(x, key_top, key_w, key_h, 1.5 * mm, stroke=1, fill=1)

            # Libellés : nom français + octave.
            self.c.setFillColor(self._contrast_color(note.color))
            self.c.setFont("Helvetica-Bold", float(legend.get("font_size", 8)))
            self.c.drawCentredString(x + key_w / 2, key_top + key_h * 0.55, note.name)
            self.c.setFont("Helvetica", float(legend.get("font_size", 8)) - 1)
            self.c.drawCentredString(x + key_w / 2, key_top + key_h * 0.28, note.label_en)
            x += key_w + gap

    @staticmethod
    def _contrast_color(hex_color: str) -> colors.Color:
        """Retourne noir ou blanc selon la luminance de ``hex_color``."""
        r = int(hex_color[1:3], 16) / 255.0
        g = int(hex_color[3:5], 16) / 255.0
        b = int(hex_color[5:7], 16) / 255.0
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return colors.black if luminance > 0.55 else colors.white