import json
import time
import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


class StorageManager:
    def __init__(self, config):
        self.config = config
        self.base_dir = Path(__file__).parent
        self.capture_dir = self.base_dir / config.storage.capture_dir
        self.thumb_dir = self.capture_dir / "thumbs"
        self.metadata_file = self.base_dir / "metadata.json"

        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.thumb_dir.mkdir(parents=True, exist_ok=True)

        self._metadata = self._load_metadata()
        logger.info(f"Storage ready: {len(self._metadata)} existing photos")

    def _load_metadata(self) -> dict:
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                logger.warning("Corrupt metadata.json, starting fresh")
        return {}

    def _save_metadata_file(self):
        tmp = self.metadata_file.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(self._metadata, f, indent=2)
        tmp.rename(self.metadata_file)

    def next_capture_path(self) -> Path:
        timestamp = int(time.time() * 1000)
        return self.capture_dir / f"bird_{timestamp}.jpg"

    def create_thumbnail(self, photo_path: Path) -> Path:
        thumb_path = self.thumb_dir / photo_path.name
        img = Image.open(photo_path)
        img.thumbnail(self.config.storage.thumbnail_size)
        img.save(str(thumb_path), "JPEG", quality=70)
        return thumb_path

    def save_metadata(self, photo_id: str, metadata: dict):
        self._metadata[photo_id] = metadata
        self._save_metadata_file()

    def get_photos(self, limit=50, offset=0) -> list:
        sorted_ids = sorted(
            self._metadata.keys(),
            key=lambda k: self._metadata[k].get("timestamp", 0),
            reverse=True,
        )
        results = []
        for photo_id in sorted_ids[offset : offset + limit]:
            meta = self._metadata[photo_id]
            results.append({
                "id": photo_id,
                "filename": f"{photo_id}.jpg",
                "thumbnail": f"thumbs/{photo_id}.jpg",
                "timestamp": meta.get("timestamp"),
                "mse": meta.get("mse"),
                "species": meta.get("species"),
            })
        return results

    def get_photo_count(self) -> int:
        return len(self._metadata)

    def get_metadata(self, photo_id: str) -> dict:
        return self._metadata.get(photo_id, {})

    def enforce_cap(self):
        while len(self._metadata) > self.config.storage.max_photos:
            oldest_id = min(
                self._metadata.keys(),
                key=lambda k: self._metadata[k].get("timestamp", 0),
            )
            photo_path = self.capture_dir / f"{oldest_id}.jpg"
            thumb_path = self.thumb_dir / f"{oldest_id}.jpg"
            photo_path.unlink(missing_ok=True)
            thumb_path.unlink(missing_ok=True)
            del self._metadata[oldest_id]
            logger.info(f"Evicted oldest photo: {oldest_id}")
        self._save_metadata_file()
