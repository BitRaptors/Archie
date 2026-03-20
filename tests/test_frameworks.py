"""Tests for archie.engine.frameworks — framework detection."""
from archie.engine.frameworks import detect_frameworks
from archie.engine.models import DependencyEntry, FileEntry


def test_detect_nextjs():
    """next dep + react dep should both be detected."""
    deps = [
        DependencyEntry(name="next", version="14.0.0"),
        DependencyEntry(name="react", version="18.2.0"),
    ]
    signals = detect_frameworks([], deps)
    names = {s.name for s in signals}
    assert "Next.js" in names
    assert "React" in names
    assert len(signals) == 2


def test_detect_fastapi():
    deps = [DependencyEntry(name="fastapi", version="0.110.0")]
    signals = detect_frameworks([], deps)
    assert len(signals) == 1
    assert signals[0].name == "FastAPI"
    assert signals[0].confidence == 0.9


def test_detect_django():
    """manage.py file + django dep should yield confidence > 0.7."""
    files = [FileEntry(path="manage.py")]
    deps = [DependencyEntry(name="django", version="5.0")]
    signals = detect_frameworks(files, deps)
    assert len(signals) == 1
    assert signals[0].name == "Django"
    # dep gives 0.9, file bumps by 0.1 -> 1.0
    assert signals[0].confidence == 1.0
    assert len(signals[0].evidence) == 2


def test_detect_nothing():
    """A repo with only readme.txt should yield no signals."""
    files = [FileEntry(path="readme.txt")]
    signals = detect_frameworks(files, [])
    assert signals == []


def test_detect_flutter():
    """pubspec.yaml + lib/main.dart (Flutter pattern)."""
    files = [
        FileEntry(path="pubspec.yaml"),
        FileEntry(path="lib/main.dart"),
    ]
    signals = detect_frameworks(files, [])
    names = {s.name for s in signals}
    assert "Flutter" in names


def test_detect_multiple_frameworks():
    """FastAPI backend + Next.js frontend detected together."""
    deps = [
        DependencyEntry(name="fastapi", version="0.110.0"),
        DependencyEntry(name="next", version="14.0.0"),
    ]
    signals = detect_frameworks([], deps)
    names = {s.name for s in signals}
    assert "FastAPI" in names
    assert "Next.js" in names
    assert len(signals) == 2
