from pathlib import Path

from fixtrace.services.stack_detector import StackDetector


def test_detects_python_pytest_and_fastapi(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["fastapi", "pytest"]\n',
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text("from fastapi import FastAPI\n", encoding="utf-8")
    (tmp_path / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")

    profile = StackDetector().detect(tmp_path)

    assert profile.primary_language == "Python"
    assert profile.frameworks == ["pytest", "FastAPI"]
    assert profile.test_command is not None
    assert profile.confidence >= 0.9


def test_ignores_generated_dependency_directories(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")
    node_modules = tmp_path / "node_modules" / "dependency"
    node_modules.mkdir(parents=True)
    for index in range(10):
        (node_modules / f"file{index}.js").write_text("export {};\n", encoding="utf-8")

    profile = StackDetector().detect(tmp_path)

    assert profile.primary_language == "Python"


def test_detector_ignores_only_repository_relative_excluded_directories(tmp_path: Path) -> None:
    repository = tmp_path / ".fixtrace" / "workspaces" / "run" / "repo"
    repository.mkdir(parents=True)
    (repository / "main.py").write_text("print('ok')\n", encoding="utf-8")

    profile = StackDetector().detect(repository)

    assert profile.primary_language == "Python"
