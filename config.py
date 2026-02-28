import yaml
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CameraConfig:
    main_resolution: tuple = (1920, 1080)
    lores_resolution: tuple = (320, 240)
    framerate: int = 30
    jpeg_quality: int = 85
    stream_quality: int = 70
    scaler_crop: tuple = None


@dataclass
class MotionConfig:
    enabled: bool = True
    mse_threshold: float = 15.0
    cooldown_seconds: float = 10.0
    warmup_seconds: float = 10.0
    adaptive_multiplier: float = 5.0


@dataclass
class StorageConfig:
    capture_dir: str = "captures"
    max_photos: int = 5000
    thumbnail_size: tuple = (320, 240)


@dataclass
class VisionConfig:
    enabled: bool = False
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 256
    active_start: str = "06:45"
    active_end: str = "18:30"


@dataclass
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 5000


@dataclass
class BirdcamConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    motion: MotionConfig = field(default_factory=MotionConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    web: WebConfig = field(default_factory=WebConfig)


def load_config(path: Path = None) -> BirdcamConfig:
    if path is None:
        path = Path(__file__).parent / "config.yaml"
    config = BirdcamConfig()
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        if "camera" in data:
            for k, v in data["camera"].items():
                if k in ("main_resolution", "lores_resolution", "scaler_crop"):
                    v = tuple(v) if v else None
                setattr(config.camera, k, v)
        if "motion" in data:
            for k, v in data["motion"].items():
                setattr(config.motion, k, v)
        if "storage" in data:
            for k, v in data["storage"].items():
                if k == "thumbnail_size":
                    v = tuple(v)
                setattr(config.storage, k, v)
        if "vision" in data:
            for k, v in data["vision"].items():
                setattr(config.vision, k, v)
        if "web" in data:
            for k, v in data["web"].items():
                setattr(config.web, k, v)
    return config
