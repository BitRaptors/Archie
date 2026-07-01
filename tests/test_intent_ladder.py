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


def test_save_branch_record_symlink_refused(tmp_path):
    """C2: symlink at the record path must NOT be followed — target untouched."""
    ad = tmp_path / ".archie"
    (ad / "intent").mkdir(parents=True)

    # Create a target file with sentinel content
    target = tmp_path / "secret.txt"
    target.write_text("ORIGINAL")

    # Place a symlink where the record would go
    spec = it.normalize("do Y", source="prompt", ticket_ids=[])
    record_p = it._record_path(ad, "feature/sym")
    record_p.symlink_to(target)

    # save_branch_record must not follow the symlink
    it.save_branch_record(ad, "feature/sym", spec)

    # The TARGET must still have its original content
    assert target.read_text() == "ORIGINAL", "symlink was followed — target was clobbered"


def test_save_branch_record_perms(tmp_path):
    """C2: record file must be created with mode 0o600."""
    ad = tmp_path / ".archie"
    ad.mkdir()
    spec = it.normalize("do Z", source="prompt", ticket_ids=[])
    it.save_branch_record(ad, "perms-branch", spec)
    record_p = it._record_path(ad, "perms-branch")
    assert record_p.stat().st_mode & 0o777 == 0o600, (
        f"Expected 0o600, got {oct(record_p.stat().st_mode & 0o777)}"
    )


def test_equal_rank_merges_not_replace(tmp_path):
    """C3: equal-rank second save must merge, not overwrite."""
    ad = tmp_path / ".archie"
    ad.mkdir()

    # First save: prompt with ticket + acceptance_criteria
    spec1 = it.normalize("task text", source="prompt", ticket_ids=["A-1"])
    spec1["acceptance_criteria"] = [{"id": "ac1", "text": "must work"}]
    it.save_branch_record(ad, "feature/merge", spec1)

    # Second save: pr_body (rank 2 == prompt rank 2) with empty ids/criteria
    spec2 = it.normalize("pr body text", source="pr_body", ticket_ids=[])
    spec2["acceptance_criteria"] = []
    it.save_branch_record(ad, "feature/merge", spec2)

    loaded = it.load_branch_record(ad, "feature/merge")
    assert "A-1" in loaded["ticket_ids"], "ticket_ids lost after equal-rank merge"
    assert any(ac.get("id") == "ac1" for ac in loaded["acceptance_criteria"]), (
        "acceptance_criteria lost after equal-rank merge"
    )


def test_record_path_no_collision(tmp_path):
    """C4: branches 'a/b' and 'a__b' must produce different files."""
    ad = tmp_path / ".archie"
    ad.mkdir()

    spec_ab = it.normalize("branch a/b", source="prompt", ticket_ids=["X-1"])
    spec_a__b = it.normalize("branch a__b", source="prompt", ticket_ids=["X-2"])

    it.save_branch_record(ad, "a/b", spec_ab)
    it.save_branch_record(ad, "a__b", spec_a__b)

    loaded_ab = it.load_branch_record(ad, "a/b")
    loaded_a__b = it.load_branch_record(ad, "a__b")

    assert loaded_ab["raw"] == "branch a/b", "a/b record corrupted"
    assert loaded_a__b["raw"] == "branch a__b", "a__b record corrupted"
    assert loaded_ab["raw"] != loaded_a__b["raw"], "path collision: both branches share a file"
