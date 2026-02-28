import io
import logging
from threading import Condition, Lock

from PIL import Image
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput

logger = logging.getLogger(__name__)


class StreamingOutput(io.BufferedIOBase):
    """Thread-safe buffer for MJPEG frames."""

    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class CameraManager:
    def __init__(self, config):
        self.config = config
        self.picam2 = Picamera2()
        self.stream_output = StreamingOutput()
        self._capture_lock = Lock()

        main_size = tuple(config.camera.main_resolution)
        lores_size = tuple(config.camera.lores_resolution)

        video_config = self.picam2.create_video_configuration(
            main={"size": main_size, "format": "RGB888"},
            lores={"size": lores_size, "format": "YUV420"},
        )
        self.picam2.configure(video_config)
        logger.info(f"Camera configured: main={main_size}, lores={lores_size}")

    def start(self):
        encoder = MJPEGEncoder()
        self.picam2.start_recording(encoder, FileOutput(self.stream_output))
        logger.info("Camera started with MJPEG streaming")

        # Apply digital zoom / crop if configured
        if self.config.camera.scaler_crop:
            crop = tuple(self.config.camera.scaler_crop)
            self.picam2.set_controls({"ScalerCrop": crop})
            logger.info(f"ScalerCrop applied: {crop}")

    def stop(self):
        self.picam2.stop_recording()
        logger.info("Camera stopped")

    def get_lores_frame(self):
        w, h = self.config.camera.lores_resolution
        return self.picam2.capture_array("lores")[:h, :w]

    def capture_still(self, save_path, quality=85):
        with self._capture_lock:
            rgb_array = self.picam2.capture_array("main")
            img = Image.fromarray(rgb_array)
            img.save(str(save_path), "JPEG", quality=quality)
            logger.info(f"Captured still: {save_path}")
            return img

    def generate_mjpeg(self):
        while True:
            with self.stream_output.condition:
                self.stream_output.condition.wait()
                frame = self.stream_output.frame
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
