from pathlib import Path
from typing import Any, Protocol


class UploadStorage(Protocol):
    upload_dir: Path

    def save(self, filename: str, content_hash: str, content: bytes) -> Path: ...


class PdfAnalysis(Protocol):
    def analyze(
        self, source: bytes | str | Path, check_signature_region: bool = False
    ) -> dict: ...


class CrewRunner(Protocol):
    async def run(self, inputs: dict, task_callback: Any = None) -> Any: ...


class PdfExporter(Protocol):
    def export(self, payload: dict) -> bytes: ...
