"""Tests du parseur ABC (abc_parser.py)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from abc_parser import (  # noqa: E402
    ABCParseError,
    BarEvent,
    NoteEvent,
    OutOfRangeError,
    parse_abc,
)
from config import load_config  # noqa: E402


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def test_parse_basic_melody(cfg):
    abc = "X:1\nT:Test\nM:4/4\nL:1/4\nK:C\nC D E F |]\n"
    score = parse_abc(abc, cfg)
    assert score.title == "Test"
    assert score.meter == "4/4"
    notes = score.notes
    assert [n.note.label_en for n in notes] == ["C4", "D4", "E4", "F4"]
    assert any(isinstance(e, BarEvent) for e in score.events)


def test_octave_marker_upper_c_is_c5(cfg):
    abc = "X:1\nT:Test\nM:4/4\nL:1/4\nK:C\nc2 C2 |]\n"
    score = parse_abc(abc, cfg)
    labels = [n.note.label_en for n in score.notes]
    assert labels == ["C5", "C4"]


def test_out_of_range_transpose(cfg):
    """Une note hors gamme est repliée dans Do4..Do5 par défaut."""
    abc = "X:1\nT:Test\nM:4/4\nL:1/4\nK:C\ne f g a |]\n"  # une octave trop haut
    score = parse_abc(abc, cfg)
    labels = [n.note.label_en for n in score.notes]
    assert labels == ["E4", "F4", "G4", "A4"]


def test_out_of_range_skip(cfg):
    """Politique 'skip' : la note hors gamme est ignorée... mais ici tout est
    transposable ; on teste donc une note impossible à ramener exactement.
    """
    abc = "X:1\nT:Test\nM:4/4\nL:1/4\nK:C\n^C D E F |]\n"
    score = parse_abc(abc, cfg)
    # Do#4 est replié sur la touche la plus proche (Do4 ou Ré4).
    assert score.notes[0].note.label_en in {"C4", "D4"}


def test_out_of_range_error_policy():
    cfg = load_config()
    cfg.raw["policy"]["out_of_range"] = "error"
    abc = "X:1\nT:Test\nM:4/4\nL:1/4\nK:C\n^C |]\n"
    with pytest.raises(OutOfRangeError):
        parse_abc(abc, cfg)


def test_rests_are_parsed(cfg):
    abc = "X:1\nT:Test\nM:4/4\nL:1/4\nK:C\nC z D z |]\n"
    score = parse_abc(abc, cfg)
    rests = [n for n in score.notes if n.is_rest]
    assert len(rests) == 2


def test_headers_are_read(cfg):
    abc = "X:1\nT:Titre\nC:Composit\nM:3/4\nL:1/8\nQ:120\nK:G\nG A B |]\n"
    score = parse_abc(abc, cfg)
    assert score.title == "Titre"
    assert score.composer == "Composit"
    assert score.meter == "3/4"
    assert score.default_length == "1/8"
    assert score.key == "G"
    assert score.tempo == "120"


def test_duration_scaling(cfg):
    """L:1/4 + '2' -> durée 1/2 (blanche)."""
    abc = "X:1\nT:Test\nM:4/4\nL:1/4\nK:C\nC2 D |]\n"
    score = parse_abc(abc, cfg)
    assert pytest.approx(score.notes[0].duration) == 0.5
    assert pytest.approx(score.notes[1].duration) == 0.25


def test_comments_and_annotations_ignored(cfg):
    abc = 'X:1\nT:Test\nM:4/4\nL:1/4\nK:C\nC "Am" D % commentaire\nE F |]\n'
    score = parse_abc(abc, cfg)
    assert [n.note.label_en for n in score.notes] == ["C4", "D4", "E4", "F4"]


def test_missing_body_raises(cfg):
    with pytest.raises(ABCParseError):
        parse_abc("X:1\nT:Vide\n", cfg)


def test_all_sample_files_parse(cfg):
    """Tous les fichiers de samples/ doivent être parsables."""
    samples = os.path.join(cfg.base_dir, "samples")
    files = [f for f in os.listdir(samples) if f.endswith(".abc")]
    assert files, "Aucun fichier d'exemple trouvé."
    for name in files:
        with open(os.path.join(samples, name), encoding="utf-8") as fh:
            score = parse_abc(fh.read(), cfg)
        assert score.note_count > 0
        # Toutes les notes doivent appartenir à la gamme C4..C5.
        for note in score.notes:
            if note.note:
                assert note.note.label_en in {"C4", "D4", "E4", "F4",
                                              "G4", "A4", "B4", "C5"}