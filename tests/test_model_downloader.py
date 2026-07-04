import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_interviewer.config import (
    DEFAULT_MODEL_ID,
    MODEL_INSTALL_MARKER,
    TOKENIZER_MODEL_ID,
    is_model_installed,
    model_dir_name,
)
from ai_interviewer.model_downloader import (
    DownloadCancelled,
    DownloadPlan,
    ModelDownloadError,
    ModelDownloader,
    RepoPlan,
    check_disk_space,
    format_bytes,
    plan_download,
    required_repo_ids,
    write_install_marker,
)


def _install(model_root: Path, model_id: str) -> Path:
    model_dir = model_root / model_dir_name(model_id)
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / MODEL_INSTALL_MARKER).write_text("{}", encoding="utf-8")
    return model_dir


def test_required_repo_ids_includes_model_and_tokenizer(tmp_path) -> None:
    repos = required_repo_ids(tmp_path, DEFAULT_MODEL_ID)
    assert repos == (DEFAULT_MODEL_ID, TOKENIZER_MODEL_ID)


def test_required_repo_ids_skips_installed(tmp_path) -> None:
    _install(tmp_path, TOKENIZER_MODEL_ID)
    assert required_repo_ids(tmp_path, DEFAULT_MODEL_ID) == (DEFAULT_MODEL_ID,)

    _install(tmp_path, DEFAULT_MODEL_ID)
    assert required_repo_ids(tmp_path, DEFAULT_MODEL_ID) == ()


def test_plan_download_uses_hub_metadata(tmp_path) -> None:
    class FakeApi:
        def model_info(self, repo_id, revision, files_metadata):
            assert files_metadata is True
            return SimpleNamespace(
                siblings=[SimpleNamespace(size=100), SimpleNamespace(size=50)]
            )

    plan = plan_download(tmp_path, DEFAULT_MODEL_ID, hf_api=FakeApi())

    assert plan.total_bytes == 300  # two repos x 150 bytes
    assert {repo.repo_id for repo in plan.repos} == {DEFAULT_MODEL_ID, TOKENIZER_MODEL_ID}
    assert all(repo.file_count == 2 for repo in plan.repos)


def test_plan_download_raises_on_metadata_failure(tmp_path) -> None:
    class BrokenApi:
        def model_info(self, repo_id, revision, files_metadata):
            raise OSError("offline")

    with pytest.raises(ModelDownloadError):
        plan_download(tmp_path, DEFAULT_MODEL_ID, hf_api=BrokenApi())


def test_check_disk_space_accounts_for_existing_bytes(tmp_path) -> None:
    target = tmp_path / "models" / model_dir_name(DEFAULT_MODEL_ID)
    target.mkdir(parents=True)
    (target / "partial.bin").write_bytes(b"x" * 600)
    plan = DownloadPlan(
        model_id=DEFAULT_MODEL_ID,
        repos=(
            RepoPlan(
                repo_id=DEFAULT_MODEL_ID,
                revision="rev",
                target_dir=target,
                total_bytes=1000,
                file_count=1,
            ),
        ),
    )

    ok, required, free = check_disk_space(tmp_path / "models", plan)

    assert required == int(400 * 1.2)
    assert ok is True
    assert free > 0


def test_write_install_marker_makes_model_installed(tmp_path) -> None:
    target = tmp_path / model_dir_name(DEFAULT_MODEL_ID)
    target.mkdir(parents=True)

    write_install_marker(target, DEFAULT_MODEL_ID, "abc123")

    assert is_model_installed(tmp_path, DEFAULT_MODEL_ID)
    payload = json.loads((target / MODEL_INSTALL_MARKER).read_text(encoding="utf-8"))
    assert payload["repo_id"] == DEFAULT_MODEL_ID
    assert payload["revision"] == "abc123"
    assert payload["license"] == "apache-2.0"


def _plan_for(tmp_path: Path) -> DownloadPlan:
    return DownloadPlan(
        model_id=DEFAULT_MODEL_ID,
        repos=(
            RepoPlan(
                repo_id=DEFAULT_MODEL_ID,
                revision="rev-a",
                target_dir=tmp_path / model_dir_name(DEFAULT_MODEL_ID),
                total_bytes=100,
                file_count=1,
            ),
            RepoPlan(
                repo_id=TOKENIZER_MODEL_ID,
                revision="rev-b",
                target_dir=tmp_path / model_dir_name(TOKENIZER_MODEL_ID),
                total_bytes=50,
                file_count=1,
            ),
        ),
    )


def _run_downloader(downloader: ModelDownloader, fake_snapshot, timeout: float = 5.0) -> None:
    import ai_interviewer.model_downloader as module

    class FakeHub(SimpleNamespace):
        pass

    def fake_download_all(self=downloader):
        tqdm_class = None
        for repo in self.plan.repos:
            if self._cancel_event.is_set():
                raise DownloadCancelled()
            self._download_repo(repo, fake_snapshot, tqdm_class)
            module.write_install_marker(repo.target_dir, repo.repo_id, repo.revision)
        if self.plan.repos:
            module.record_model_sources(self.plan.repos[0].target_dir.parent, self.plan.repos)

    downloader._download_all = fake_download_all  # bypass the hub import
    downloader.start()
    deadline = time.monotonic() + timeout
    while not downloader._finished_event.is_set() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert downloader._finished_event.is_set(), "downloader did not finish in time"


def test_downloader_success_writes_markers_and_sources(tmp_path) -> None:
    plan = _plan_for(tmp_path)
    events: list[str] = []

    def fake_snapshot(repo_id, revision, local_dir, max_workers, tqdm_class):
        target = Path(local_dir)
        target.mkdir(parents=True, exist_ok=True)
        (target / "model.safetensors").write_bytes(b"x" * 10)

    downloader = ModelDownloader(
        plan,
        on_progress=lambda p: None,
        on_done=lambda: events.append("done"),
        on_error=lambda exc: events.append(f"error:{exc}"),
        on_cancelled=lambda: events.append("cancelled"),
        poll_interval=0.05,
    )
    _run_downloader(downloader, fake_snapshot)

    assert events == ["done"]
    assert is_model_installed(tmp_path, DEFAULT_MODEL_ID)
    assert is_model_installed(tmp_path, TOKENIZER_MODEL_ID)
    sources = (tmp_path / "model_sources.txt").read_text(encoding="utf-8")
    assert DEFAULT_MODEL_ID in sources
    assert "rev-a" in sources


def test_downloader_retries_then_fails(tmp_path) -> None:
    plan = _plan_for(tmp_path)
    events: list[str] = []
    attempts = {"count": 0}

    def flaky_snapshot(repo_id, revision, local_dir, max_workers, tqdm_class):
        attempts["count"] += 1
        raise OSError("network down")

    downloader = ModelDownloader(
        plan,
        on_progress=lambda p: None,
        on_done=lambda: events.append("done"),
        on_error=lambda exc: events.append("error"),
        on_cancelled=lambda: events.append("cancelled"),
        poll_interval=0.05,
    )
    downloader.RETRY_BACKOFF_SECONDS = (0.01, 0.01)
    _run_downloader(downloader, flaky_snapshot)

    assert events == ["error"]
    assert attempts["count"] == ModelDownloader.RETRIES_PER_REPO
    assert not is_model_installed(tmp_path, DEFAULT_MODEL_ID)


def test_downloader_cancel_stops_between_repos(tmp_path) -> None:
    plan = _plan_for(tmp_path)
    events: list[str] = []
    downloader: ModelDownloader | None = None

    def cancelling_snapshot(repo_id, revision, local_dir, max_workers, tqdm_class):
        target = Path(local_dir)
        target.mkdir(parents=True, exist_ok=True)
        (target / "model.safetensors").write_bytes(b"x" * 10)
        downloader.cancel()  # cancel lands after the first repo completes

    downloader = ModelDownloader(
        plan,
        on_progress=lambda p: None,
        on_done=lambda: events.append("done"),
        on_error=lambda exc: events.append("error"),
        on_cancelled=lambda: events.append("cancelled"),
        poll_interval=0.05,
    )
    _run_downloader(downloader, cancelling_snapshot)

    assert events == ["cancelled"]
    assert is_model_installed(tmp_path, DEFAULT_MODEL_ID)
    assert not is_model_installed(tmp_path, TOKENIZER_MODEL_ID)


def test_cancel_tqdm_raises_on_update() -> None:
    from ai_interviewer.model_downloader import _make_cancel_tqdm

    cancel = threading.Event()
    tqdm_class = _make_cancel_tqdm(cancel)
    bar = tqdm_class(total=10)
    bar.update(1)

    cancel.set()
    with pytest.raises(DownloadCancelled):
        bar.update(1)


def test_format_bytes_readable() -> None:
    assert format_bytes(512) == "512 B"
    assert format_bytes(2_500_000_000) == "2.3 GB"
