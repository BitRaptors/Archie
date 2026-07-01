import json
from pathlib import Path
import sys

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import intent as it  # noqa: E402


def test_ticket_ids_from_branch_and_body():
    ids = it.ticket_ids_from("feature/ARCH-123-export", "closes ARCH-124", ["fix ARCH-123"])
    assert set(ids) == {"ARCH-123", "ARCH-124"}


def test_save_and_load_branch_record(tmp_path):
    ad = tmp_path / ".archie"
    ad.mkdir()
    spec = it.normalize("do X", source="prompt", ticket_ids=[])
    it.save_branch_record(ad, "feature/x", spec)
    got = it.load_branch_record(ad, "feature/x")
    assert got["raw"] == "do X"


def test_save_does_not_downgrade_confidence(tmp_path):
    ad = tmp_path / ".archie"
    ad.mkdir()
    it.save_branch_record(ad, "b", it.normalize("t", source="linear", ticket_ids=["A-1"]))
    it.save_branch_record(ad, "b", it.normalize("p", source="prompt", ticket_ids=[]))
    assert it.load_branch_record(ad, "b")["source"] == "linear"
