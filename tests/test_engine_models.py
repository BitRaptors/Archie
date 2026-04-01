from archie.engine.models import RawScan, FileEntry, DependencyEntry, FrameworkSignal

def test_raw_scan_empty():
    scan = RawScan()
    assert scan.file_tree == []
    assert scan.token_counts == {}
    assert scan.dependencies == []
    assert scan.framework_signals == []
    assert scan.import_graph == {}
    assert scan.file_hashes == {}
    assert scan.entry_points == []

def test_file_entry():
    entry = FileEntry(path="src/main.py", size=1024, last_modified=1710000000.0)
    assert entry.path == "src/main.py"
    assert entry.size == 1024

def test_dependency_entry():
    dep = DependencyEntry(name="fastapi", version=">=0.104.0", source="requirements.txt")
    assert dep.name == "fastapi"
    assert dep.source == "requirements.txt"

def test_framework_signal():
    sig = FrameworkSignal(name="Next.js", version="14", confidence=0.9, evidence=["next.config.js"])
    assert sig.name == "Next.js"
    assert sig.confidence == 0.9
