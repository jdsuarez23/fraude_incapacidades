import os
import tempfile
from pathlib import Path


class LocalUploadStorage:
    def __init__(self, upload_dir: Path | None = None):
        self.upload_dir = upload_dir or Path(
            os.environ.get(
                "UPLOAD_DIR",
                Path(tempfile.gettempdir())
                / "fraude_incapacidades"
                / "uploads",
            )
        )
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, content_hash: str, content: bytes) -> Path:
        path = self.upload_dir / f"{content_hash[:12]}_{Path(filename).name}"
        path.write_bytes(content)
        return path
