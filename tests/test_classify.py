"""Tests for workflow.classify_input — universal-attach role detection."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from femrep.workflow import classify_input


@pytest.mark.parametrize("name,role", [
    ("model.rst", "result"),
    ("model.rth", "result"),
    ("solve.f06", "result"),
    ("solve.op2", "result"),
    ("solve.mntr", "log"),
    ("solve.out", "log"),
    ("solve.log", "log"),
    ("gci_runs.json", "gci"),
    ("my_gci.json", "gci"),
    ("template.json", "unknown"),   # a non-GCI .json must not be fed to run_gci
    ("results.json", "unknown"),
    ("batch.json", "unknown"),
    ("deck.dat", "deck"),
    ("deck.bdf", "deck"),
    ("deck.inp", "deck"),
    ("deck.cdb", "deck"),
    ("notes.txt", "unknown"),
    ("image.png", "unknown"),
    ("archive", "unknown"),
])
def test_classify_input_roles(name, role):
    assert classify_input(name) == role


def test_classify_input_case_insensitive():
    assert classify_input("MODEL.RST") == "result"
    assert classify_input("Solve.F06") == "result"
    assert classify_input("Deck.BDF") == "deck"
    assert classify_input("GCI_RUNS.JSON") == "gci"


def test_classify_input_accepts_path_object():
    assert classify_input(Path("/tmp/a/b/run.op2")) == "result"
