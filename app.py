#!/usr/bin/env python3
"""Birdcam - Raspberry Pi bird feeder camera system."""

import signal
import sys
import logging
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from config import load_config
from camera import CameraManager
from storage import StorageManager
from vision import ClaudeVision
from motion import MotionDetector
from web import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "birdcam.log"),
    ],
)
logger = logging.getLogger("birdcam")


def main():
    config = load_config()

    # 1. Storage
    storage = StorageManager(config)

    # 2. Camera
    camera = CameraManager(config)
    camera.start()

    # 3. Vision (optional)
    vision = None
    if config.vision.enabled:
        try:
            vision = ClaudeVision(config)
            logger.info("Claude Vision module loaded")
        except Exception:
            logger.warning("Vision module failed to initialize, continuing without it")

    # 4. Motion detection
    motion = MotionDetector(camera, storage, vision, config)
    motion.start()

    # 5. Flask web app
    app = create_app(camera, storage, motion, vision, config)

    # Graceful shutdown
    def shutdown(signum, frame):
        logger.info("Shutting down...")
        motion.stop()
        camera.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    logger.info(f"Birdcam starting on http://0.0.0.0:{config.web.port}")
    app.run(
        host=config.web.host,
        port=config.web.port,
        threaded=True,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
