import time
import yaml
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, render_template, jsonify, request, send_from_directory


def create_app(camera_manager, storage_manager, motion_detector, vision_module, config):
    app = Flask(__name__)
    config_path = Path(__file__).parent / "config.yaml"

    @app.template_filter("datetime")
    def format_datetime(value):
        if value:
            return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
        return ""

    @app.template_filter("timeago")
    def format_timeago(value):
        if not value:
            return ""
        diff = time.time() - value
        if diff < 60:
            return f"{int(diff)}s ago"
        if diff < 3600:
            return f"{int(diff / 60)}m ago"
        if diff < 86400:
            return f"{int(diff / 3600)}h ago"
        return f"{int(diff / 86400)}d ago"

    @app.route("/")
    def index():
        photos = storage_manager.get_photos(limit=60)
        return render_template(
            "index.html",
            photos=photos,
            total_photos=storage_manager.get_photo_count(),
            motion_enabled=config.motion.enabled,
            vision_enabled=config.vision.enabled,
            multiplier=config.motion.adaptive_multiplier,
            cooldown=config.motion.cooldown_seconds,
            mse_threshold=config.motion.mse_threshold,
        )

    @app.route("/stream")
    def stream():
        return Response(
            camera_manager.generate_mjpeg(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.route("/captures/<path:filename>")
    def serve_capture(filename):
        return send_from_directory(str(storage_manager.capture_dir), filename)

    @app.route("/photo/<photo_id>")
    def photo_detail(photo_id):
        meta = storage_manager.get_metadata(photo_id)
        return render_template("photo.html", photo_id=photo_id, meta=meta)

    @app.route("/api/status")
    def api_status():
        return jsonify({
            "motion_enabled": config.motion.enabled,
            "vision_enabled": config.vision.enabled,
            "last_mse": motion_detector.last_mse if motion_detector else 0,
            "threshold": motion_detector.effective_threshold if motion_detector else 0,
            "baseline": motion_detector.baseline_mse if motion_detector else 0,
            "captures_count": motion_detector.captures_count if motion_detector else 0,
            "birds_count": motion_detector.birds_count if motion_detector else 0,
            "rejected_count": motion_detector.rejected_count if motion_detector else 0,
            "total_photos": storage_manager.get_photo_count(),
            "max_photos": config.storage.max_photos,
            "multiplier": config.motion.adaptive_multiplier,
            "cooldown": config.motion.cooldown_seconds,
        })

    @app.route("/api/photos")
    def api_photos():
        limit = int(request.args.get("limit", 60))
        offset = int(request.args.get("offset", 0))
        photos = storage_manager.get_photos(limit=limit, offset=offset)
        return jsonify({"photos": photos, "total": storage_manager.get_photo_count()})

    @app.route("/api/capture", methods=["POST"])
    def api_capture():
        photo_path = storage_manager.next_capture_path()
        camera_manager.capture_still(photo_path, quality=config.camera.jpeg_quality)
        storage_manager.create_thumbnail(photo_path)
        metadata = {"timestamp": time.time(), "mse": 0, "species": None, "detail": None}
        if vision_module and config.vision.enabled:
            try:
                result = vision_module.identify(photo_path)
                metadata["species"] = result.get("species")
                metadata["detail"] = result.get("detail")
                if not result["is_bird"]:
                    metadata["species"] = "No bird detected"
            except Exception:
                metadata["species"] = "Vision error"
        storage_manager.save_metadata(photo_path.stem, metadata)
        return jsonify({"success": True, "photo_id": photo_path.stem, "species": metadata["species"]})

    @app.route("/api/check-angle", methods=["POST"])
    def api_check_angle():
        if not vision_module:
            return jsonify({"error": "Vision module not available"}), 503
        photo_path = storage_manager.next_capture_path()
        camera_manager.capture_still(photo_path, quality=config.camera.jpeg_quality)
        storage_manager.create_thumbnail(photo_path)
        try:
            analysis = vision_module.check_camera_angle(photo_path)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        metadata = {"timestamp": time.time(), "mse": 0, "species": "angle-check"}
        storage_manager.save_metadata(photo_path.stem, metadata)
        return jsonify({"success": True, "photo_id": photo_path.stem, "analysis": analysis})

    @app.route("/api/settings", methods=["POST"])
    def api_settings():
        """Update motion detection settings live."""
        data = request.get_json()
        changed = []

        if "multiplier" in data:
            val = float(data["multiplier"])
            config.motion.adaptive_multiplier = val
            changed.append(f"multiplier={val}")

        if "cooldown" in data:
            val = float(data["cooldown"])
            config.motion.cooldown_seconds = val
            changed.append(f"cooldown={val}")

        if "mse_threshold" in data:
            val = float(data["mse_threshold"])
            config.motion.mse_threshold = val
            changed.append(f"mse_threshold={val}")

        # Persist to config.yaml
        if changed:
            try:
                with open(config_path) as f:
                    cfg = yaml.safe_load(f)
                cfg["motion"]["adaptive_multiplier"] = config.motion.adaptive_multiplier
                cfg["motion"]["cooldown_seconds"] = config.motion.cooldown_seconds
                cfg["motion"]["mse_threshold"] = config.motion.mse_threshold
                with open(config_path, "w") as f:
                    yaml.dump(cfg, f, default_flow_style=False)
            except Exception:
                pass

        return jsonify({"success": True, "changed": changed})

    return app
