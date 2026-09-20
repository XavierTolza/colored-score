"""Tests de la configuration (config.py)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import ConfigError, load_config  # noqa: E402


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def test_load_default_config(cfg):
    assert cfg.page_size_name() == "A4"
    assert cfg.orientation() == "portrait"
    assert len(cfg.notes) == 8


def test_strict_color_mapping(cfg):
    """La correspondance des 8 touches doit être exacte et dans l'ordre."""
    expected = [
        ("C", "#E51937"), ("D", "#F37023"), ("E", "#FFD100"), ("F", "#5BB847"),
        ("G", "#00AEEF"), ("A", "#0054A6"), ("B", "#B552A0"), ("c", "#D81B60"),
    ]
    ordered = cfg.ordered_notes()
    assert [(n.abc, n.color) for n in ordered] == expected
    assert [n.order for n in ordered] == [1, 2, 3, 4, 5, 6, 7, 8]


def test_note_by_abc(cfg):
    assert cfg.note_by_abc("G").name == "Sol"
    assert cfg.note_by_abc("c").label_en == "C5"


def test_note_by_abc_unknown(cfg):
    with pytest.raises(ConfigError):
        cfg.note_by_abc("H")


def test_rgb_conversion(cfg):
    r, g, b = cfg.note_by_abc("C").rgb
    # #E51937 -> (0xE5, 0x19, 0x37) / 255
    assert (round(r, 4), round(g, 4), round(b, 4)) == (0.898, 0.098, 0.2157)


def test_invalid_config_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("notes: {}\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(str(bad))


def test_invalid_color_raises(tmp_path):
    content = """
notes:
  C: {name: Do, octave: 4, order: 1, color: "notacolor"}
  D: {name: Re, octave: 4, order: 2, color: "#F37023"}
  E: {name: Mi, octave: 4, order: 3, color: "#FFD100"}
  F: {name: Fa, octave: 4, order: 4, color: "#5BB847"}
  G: {name: Sol, octave: 4, order: 5, color: "#00AEEF"}
  A: {name: La, octave: 4, order: 6, color: "#0054A6"}
  B: {name: Si, octave: 4, order: 7, color: "#B552A0"}
  c: {name: Do, octave: 5, order: 8, color: "#D81B60"}
layout:
  page_size: A4
  orientation: portrait
  staff: {space: 3.2}
colors: {}
"""
    bad = tmp_path / "bad_color.yaml"
    bad.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(str(bad))


def test_missing_file_raises():
    with pytest.raises(ConfigError):
        load_config("/nonexistent/config.yaml")