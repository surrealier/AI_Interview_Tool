from __future__ import annotations

import json
import logging
import shutil
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ai_interviewer.config import (
    DEFAULT_MODEL_ID,
    LARGE_MODEL_ID,
    MODEL_INSTALL_MARKER,
    TOKENIZER_MODEL_ID,
    is_model_installed,
    model_dir_name,
)


logger = logging.getLogger(__name__)


# Pinned upstream revisions. All three repos are Apache-2.0 (declared in each
# model card); MODEL_LICENSES.md documents the same table for the release.
MODEL_REVISIONS: dict[str, str] = {
    DEFAULT_MODEL_ID: "85e237c12c027371202489a0ec509ded67b5e4b5",
    LARGE_MODEL_ID: "0c0e3051f131929182e2c023b9537f8b1c68adfe",
    TOKENIZER_MODEL_ID: "7dd38ad4e9bad454aae9cd937d0cd577604fe229",
}

MODEL_LICENSE = "apache-2.0"

# Sizes captured with the pinned revisions; used for UI labels before the Hub
# metadata query runs (the query result replaces these for the actual plan).
APPROX_REPO_BYTES: dict[str, int] = {
    DEFAULT_MODEL_ID: 2_498_388_392,
    LARGE_MODEL_ID: 4_520_218_951,
    TOKENIZER_MODEL_ID: 682_300_739,
}

DISK_SPACE_HEADROOM = 1.2


class DownloadCancelled(Exception):
    pass


class ModelDownloadError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RepoPlan:
    repo_id: str
    revision: str
    target_dir: Path
    total_bytes: int
    file_count: int


@dataclass(frozen=True, slots=True)
class DownloadPlan:
    model_id: str
    repos: tuple[RepoPlan, ...]

    @property
    def total_bytes(self) -> int:
        return sum(repo.total_bytes for repo in self.repos)


@dataclass(frozen=True, slots=True)
class DownloadProgress:
    downloaded_bytes: int
    total_bytes: int
    speed_bps: float

    @property
    def fraction(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return min(1.0, self.downloaded_bytes / self.total_bytes)


def required_repo_ids(model_root: Path, model_id: str) -> tuple[str, ...]:
    """Repos that still need downloading for `model_id` to be usable."""
    repos: list[str] = []
    if not is_model_installed(model_root, model_id):
        repos.append(model_id)
    if not is_model_installed(model_root, TOKENIZER_MODEL_ID):
        repos.append(TOKENIZER_MODEL_ID)
    return tuple(repos)


def approx_download_bytes(model_root: Path, model_id: str) -> int:
    return sum(APPROX_REPO_BYTES.get(repo, 0) for repo in required_repo_ids(model_root, model_id))


def format_bytes(num_bytes: float) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


def directory_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def check_disk_space(model_root: Path, plan: DownloadPlan) -> tuple[bool, int, int]:
    """Return (ok, required_bytes, free_bytes).

    Required space is the not-yet-downloaded remainder with headroom for the
    hub's temporary .incomplete files.
    """
    existing = sum(directory_bytes(repo.target_dir) for repo in plan.repos)
    remaining = max(0, plan.total_bytes - existing)
    required = int(remaining * DISK_SPACE_HEADROOM)
    probe = model_root if model_root.exists() else model_root.parent
    try:
        free = shutil.disk_usage(probe).free
    except OSError:
        return True, required, 0
    return free >= required, required, free


def plan_download(model_root: Path, model_id: str, hf_api: Any | None = None) -> DownloadPlan:
    """Query the Hub for the exact files/bytes of the repos still needed."""
    repo_ids = required_repo_ids(model_root, model_id)
    if not repo_ids:
        return DownloadPlan(model_id=model_id, repos=())

    if hf_api is None:
        try:
            from huggingface_hub import HfApi
        except ImportError as exc:  # pragma: no cover - dependency error path
            raise ModelDownloadError(
                "huggingface-hub is not installed. Run: python -m pip install -r requirements-qwen.txt"
            ) from exc
        hf_api = HfApi()

    repos: list[RepoPlan] = []
    for repo_id in repo_ids:
        revision = MODEL_REVISIONS.get(repo_id, "main")
        try:
            info = hf_api.model_info(repo_id, revision=revision, files_metadata=True)
        except Exception as exc:
            raise ModelDownloadError(
                f"Could not query model metadata for {repo_id}: {exc}"
            ) from exc
        siblings = getattr(info, "siblings", None) or []
        repos.append(
            RepoPlan(
                repo_id=repo_id,
                revision=revision,
                target_dir=Path(model_root) / model_dir_name(repo_id),
                total_bytes=sum(getattr(f, "size", 0) or 0 for f in siblings),
                file_count=len(siblings),
            )
        )
    return DownloadPlan(model_id=model_id, repos=tuple(repos))


def write_install_marker(target_dir: Path, repo_id: str, revision: str) -> None:
    payload = {
        "repo_id": repo_id,
        "revision": revision,
        "license": MODEL_LICENSE,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }
    marker = target_dir / MODEL_INSTALL_MARKER
    marker.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def record_model_sources(model_root: Path, repos: tuple[RepoPlan, ...]) -> None:
    metadata_path = Path(model_root) / "model_sources.txt"
    lines = [f"downloaded_at={datetime.now(timezone.utc).isoformat()}"]
    for repo in repos:
        lines.append(f"revision={repo.revision}")
        lines.append(f"license={MODEL_LICENSE}")
        lines.append(f"model={repo.repo_id} -> {repo.target_dir}")
    with metadata_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _make_cancel_tqdm(cancel_event: threading.Event) -> Any:
    from tqdm.auto import tqdm as base_tqdm

    class CancelAwareTqdm(base_tqdm):  # type: ignore[misc, valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["disable"] = True  # windowed app: sys.stderr may be None
            super().__init__(*args, **kwargs)

        def update(self, n: int = 1) -> Any:
            if cancel_event.is_set():
                raise DownloadCancelled()
            return super().update(n)

    return CancelAwareTqdm


class ModelDownloader:
    """Download the repos of a DownloadPlan on a background thread.

    Callbacks fire on downloader threads; UI callers must marshal to the Tk
    main loop themselves (e.g. `widget.after(0, ...)`). Cancel returns the UI
    immediately; the worker stops at the next file boundary and partially
    downloaded files are reused on the next attempt (hub resume files).
    """

    RETRIES_PER_REPO = 3
    RETRY_BACKOFF_SECONDS = (2.0, 5.0)

    def __init__(
        self,
        plan: DownloadPlan,
        on_progress: Callable[[DownloadProgress], None],
        on_done: Callable[[], None],
        on_error: Callable[[Exception], None],
        on_cancelled: Callable[[], None],
        poll_interval: float = 0.7,
    ) -> None:
        self.plan = plan
        self.on_progress = on_progress
        self.on_done = on_done
        self.on_error = on_error
        self.on_cancelled = on_cancelled
        self.poll_interval = poll_interval
        self._cancel_event = threading.Event()
        self._finished_event = threading.Event()
        self._started = False

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @property
    def finished(self) -> bool:
        return self._finished_event.is_set()

    def start(self) -> None:
        if self._started:
            raise RuntimeError("ModelDownloader can only be started once.")
        self._started = True
        threading.Thread(target=self._run, daemon=True, name="model-download").start()
        threading.Thread(target=self._poll_progress, daemon=True, name="model-download-progress").start()

    def cancel(self) -> None:
        self._cancel_event.set()

    def _run(self) -> None:
        try:
            self._download_all()
        except DownloadCancelled:
            logger.info("Model download cancelled by user.")
            self._finished_event.set()
            self.on_cancelled()
        except Exception as exc:
            logger.exception("Model download failed.")
            self._finished_event.set()
            self.on_error(exc)
        else:
            self._finished_event.set()
            self.on_done()

    def _download_all(self) -> None:
        try:
            from huggingface_hub import snapshot_download
            from huggingface_hub.utils import disable_progress_bars
        except ImportError as exc:  # pragma: no cover - dependency error path
            raise ModelDownloadError(
                "huggingface-hub is not installed. Run: python -m pip install -r requirements-qwen.txt"
            ) from exc

        disable_progress_bars()  # inner byte bars would write to a missing console
        tqdm_class = _make_cancel_tqdm(self._cancel_event)

        for repo in self.plan.repos:
            if self._cancel_event.is_set():
                raise DownloadCancelled()
            self._download_repo(repo, snapshot_download, tqdm_class)
            write_install_marker(repo.target_dir, repo.repo_id, repo.revision)
        if self.plan.repos:
            record_model_sources(self.plan.repos[0].target_dir.parent, self.plan.repos)

    def _download_repo(self, repo: RepoPlan, snapshot_download: Any, tqdm_class: Any) -> None:
        last_exc: Exception | None = None
        for attempt in range(self.RETRIES_PER_REPO):
            if self._cancel_event.is_set():
                raise DownloadCancelled()
            try:
                snapshot_download(
                    repo_id=repo.repo_id,
                    revision=repo.revision,
                    local_dir=str(repo.target_dir),
                    max_workers=4,
                    tqdm_class=tqdm_class,
                )
                return
            except DownloadCancelled:
                raise
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Download attempt %d/%d for %s failed: %s",
                    attempt + 1,
                    self.RETRIES_PER_REPO,
                    repo.repo_id,
                    exc,
                )
                if attempt < self.RETRIES_PER_REPO - 1:
                    backoff = self.RETRY_BACKOFF_SECONDS[min(attempt, len(self.RETRY_BACKOFF_SECONDS) - 1)]
                    if self._cancel_event.wait(backoff):
                        raise DownloadCancelled() from None
        raise ModelDownloadError(f"Could not download {repo.repo_id}: {last_exc}") from last_exc

    def _poll_progress(self) -> None:
        started = time.monotonic()
        last_bytes = self._current_bytes()
        last_time = started
        while not self._finished_event.is_set() and not self._cancel_event.is_set():
            time.sleep(self.poll_interval)
            now = time.monotonic()
            current = self._current_bytes()
            elapsed = max(now - last_time, 1e-6)
            speed = max(0.0, (current - last_bytes) / elapsed)
            last_bytes, last_time = current, now
            if self._finished_event.is_set() or self._cancel_event.is_set():
                break
            self.on_progress(
                DownloadProgress(
                    downloaded_bytes=current,
                    total_bytes=self.plan.total_bytes,
                    speed_bps=speed,
                )
            )

    def _current_bytes(self) -> int:
        return sum(directory_bytes(repo.target_dir) for repo in self.plan.repos)
