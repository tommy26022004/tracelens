import hashlib
import json
import shutil
from pathlib import Path

from app.core.config import settings


class SourceDocuments:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or settings.source_documents_dir

    def _key(self, document_id: str) -> str:
        return hashlib.sha256(document_id.encode("utf-8")).hexdigest()

    def archive(self, document_id: str, path: Path, filename: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        key = self._key(document_id)
        shutil.copyfile(path, self.directory / f"{key}.pdf")
        metadata = {
            "document_id": document_id,
            "filename": filename,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        temporary = self.directory / f"{key}.json.tmp"
        temporary.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.directory / f"{key}.json")

    def lookup(self, document_id: str) -> tuple[Path, str] | None:
        key = self._key(document_id)
        metadata_path = self.directory / f"{key}.json"
        pdf_path = self.directory / f"{key}.pdf"
        if not metadata_path.is_file() or not pdf_path.is_file():
            return None
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("document_id") != document_id:
            return None
        return pdf_path, metadata["filename"]
