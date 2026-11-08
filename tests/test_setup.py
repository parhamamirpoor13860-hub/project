"""Milestone 1 setup verification tests."""
from pathlib import Path
from src.config import Settings, get_settings


def test_settings_defaults(tmp_path: Path):
    s = Settings(
        data_dir=tmp_path / "data",
        raw_dir=tmp_path / "data/raw",
        processed_dir=tmp_path / "data/processed",
        fixtures_dir=tmp_path / "data/fixtures",
    )
    s.ensure_dirs()
    assert s.tsetmc_base_url == "https://cdn.tsetmc.com/api"
    assert s.tsetmc_start_date == 20230321
    assert s.tsetmc_max_rps == 2.0
    assert (tmp_path / "data/raw").is_dir()
    assert (tmp_path / "data/processed").is_dir()
    assert (tmp_path / "data/fixtures").is_dir()


def test_project_files_exist():
    root = Path(__file__).resolve().parent.parent
    assert (root / ".gitignore").is_file()
    assert (root / ".env.example").is_file()
    assert (root / "docker-compose.yml").is_file()
    assert (root / "requirements.txt").is_file()
    assert (root / "docs" / "TSETMC_API.md").is_file()
    assert (root / "frontend" / "package.json").is_file()
    assert get_settings().tsetmc_timeout_seconds > 0
