import time
import logging
from collections import deque
from datetime import datetime
import numpy as np
from threading import Thread, Event

logger = logging.getLogger(__name__)


class MotionDetector:
    def __init__(self, camera_manager, storage_manager, vision_module, config):
        self.camera = camera_manager
        self.storage = storage_manager
        self.vision = vision_module
        self.config = config
        self._stop_event = Event()
        self._thread = None
        self.last_mse = 0.0
        self.last_capture_time = 0.0
        self.captures_count = 0
        self.birds_count = 0
        self.rejected_count = 0
        self.baseline_mse = 0.0
        self.effective_threshold = 0.0

    def start(self):
        if not self.config.motion.enabled:
            logger.info("Motion detection disabled in config")
            return
        self._thread = Thread(target=self._run, daemon=True, name="motion-detector")
        self._thread.start()
        logger.info(
            f"Motion detection started (min_threshold={self.config.motion.mse_threshold}, "
            f"multiplier={self.config.motion.adaptive_multiplier}x, "
            f"cooldown={self.config.motion.cooldown_seconds}s)"
        )

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _is_vision_active(self):
        """Check if current time is within the vision active window."""
        try:
            now = datetime.now()
            start_h, start_m = map(int, self.config.vision.active_start.split(":"))
            end_h, end_m = map(int, self.config.vision.active_end.split(":"))
            start_minutes = start_h * 60 + start_m
            end_minutes = end_h * 60 + end_m
            now_minutes = now.hour * 60 + now.minute
            return start_minutes <= now_minutes <= end_minutes
        except Exception:
            logger.exception("Error checking vision active window, defaulting to active")
            return True

    def _run(self):
        time.sleep(self.config.motion.warmup_seconds)
        logger.info("Motion detection warmup complete")
        prev = None
        mse_history = deque(maxlen=300)
        log_counter = 0
        multiplier = self.config.motion.adaptive_multiplier

        while not self._stop_event.is_set():
            try:
                cur = self.camera.get_lores_frame()
                if prev is not None:
                    mse = np.square(
                        np.subtract(cur.astype(np.int16), prev.astype(np.int16))
                    ).mean()
                    self.last_mse = float(mse)
                    mse_history.append(float(mse))

                    log_counter += 1
                    if log_counter >= 100:
                        if len(mse_history) >= 50:
                            recent = list(mse_history)
                            median = np.median(recent)
                            p95 = np.percentile(recent, 95)
                            threshold = max(self.config.motion.mse_threshold, median * multiplier)
                            self.baseline_mse = median
                            self.effective_threshold = threshold
                            vision_status = "active" if self._is_vision_active() else "sleeping"
                            logger.info(
                                f"MSE: median={median:.0f} p95={p95:.0f} "
                                f"threshold={threshold:.0f} | "
                                f"birds={self.birds_count} rejected={self.rejected_count} "
                                f"vision={vision_status}"
                            )
                        log_counter = 0

                    now = time.time()
                    if len(mse_history) >= 50:
                        median = np.median(list(mse_history))
                        threshold = max(self.config.motion.mse_threshold, median * multiplier)
                    else:
                        threshold = self.config.motion.mse_threshold
                    self.effective_threshold = threshold

                    if (mse > threshold and
                            now - self.last_capture_time >= self.config.motion.cooldown_seconds):
                        self._on_motion(mse, threshold)
                        self.last_capture_time = now

                prev = cur
                time.sleep(0.1)

            except Exception:
                logger.exception("Error in motion detection loop")
                time.sleep(1)

    def _on_motion(self, mse, threshold):
        self.captures_count += 1

        # Outside vision hours, skip capture entirely to save disk + API
        if self.vision and self.config.vision.enabled and not self._is_vision_active():
            logger.debug(f"Motion (MSE={mse:.0f}) outside vision hours — skipping capture")
            return

        logger.info(f"Motion! MSE={mse:.0f} (threshold={threshold:.0f}) - capturing...")
        photo_path = self.storage.next_capture_path()
        self.camera.capture_still(photo_path, quality=self.config.camera.jpeg_quality)

        if self.vision and self.config.vision.enabled:
            try:
                result = self.vision.identify(photo_path)
                if result["is_bird"]:
                    self.birds_count += 1
                    logger.info(f"BIRD: {result['species']} ({result.get('detail', '')})")
                    self.storage.create_thumbnail(photo_path)
                    metadata = {
                        "timestamp": time.time(),
                        "mse": round(mse, 2),
                        "species": result["species"],
                        "detail": result.get("detail"),
                    }
                    self.storage.save_metadata(photo_path.stem, metadata)
                    self.storage.enforce_cap()
                else:
                    self.rejected_count += 1
                    photo_path.unlink(missing_ok=True)
                    logger.info(f"No bird — deleted ({self.rejected_count} rejected total)")
            except Exception:
                logger.exception("Vision failed — keeping photo anyway")
                self.storage.create_thumbnail(photo_path)
                metadata = {
                    "timestamp": time.time(),
                    "mse": round(mse, 2),
                    "species": "Vision error",
                    "detail": None,
                }
                self.storage.save_metadata(photo_path.stem, metadata)
        else:
            self.storage.create_thumbnail(photo_path)
            metadata = {"timestamp": time.time(), "mse": round(mse, 2), "species": None}
            self.storage.save_metadata(photo_path.stem, metadata)
            self.storage.enforce_cap()
