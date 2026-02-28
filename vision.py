import base64
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

IDENTIFY_PROMPT = """\
Look at this photo from a bird feeder camera. 

If there is a bird visible:
- Reply with ONLY the species common name on the first line (e.g., "Northern Cardinal")
- On the second line, add one brief distinguishing feature

If there is NO bird visible (just trees, sky, empty feeder, etc.):
- Reply with ONLY the text: NO_BIRD

Examples of valid responses:
  Northern Cardinal
  Bright red plumage with black face mask

  NO_BIRD
"""

ANGLE_CHECK_PROMPT = (
    "This is a test photo from a bird feeder camera. Evaluate whether this "
    "camera angle and position would be good for identifying bird species "
    "that visit the feeder. Consider: distance, angle, lighting, focus area, "
    "and whether birds at the feeder would be clearly visible. Give specific "
    "suggestions for improvement if needed."
)


class ClaudeVision:
    def __init__(self, config):
        self.config = config
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    def _send_image(self, photo_path: Path, prompt: str, max_tokens: int = None) -> str:
        client = self._get_client()
        with open(photo_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        message = client.messages.create(
            model=self.config.vision.model,
            max_tokens=max_tokens or self.config.vision.max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        return message.content[0].text.strip()

    def identify(self, photo_path: Path) -> dict:
        """Returns {'is_bird': bool, 'species': str|None, 'detail': str|None}"""
        result = self._send_image(photo_path, IDENTIFY_PROMPT)
        logger.info(f"Claude response: {result}")

        if "NO_BIRD" in result.upper():
            return {"is_bird": False, "species": None, "detail": None}

        lines = result.strip().split("\n")
        species = lines[0].strip()
        detail = lines[1].strip() if len(lines) > 1 else None
        return {"is_bird": True, "species": species, "detail": detail}

    def check_camera_angle(self, photo_path: Path) -> str:
        return self._send_image(photo_path, ANGLE_CHECK_PROMPT, max_tokens=512)
