"""Small, explicit storyboard format. No network or arbitrary command input."""

from dataclasses import dataclass
import json
import math
from pathlib import Path

from PIL import Image, UnidentifiedImageError


class StoryError(ValueError):
    """A user-facing validation error."""


@dataclass(frozen=True)
class Scene:
    headline: str
    detail: str
    narration: str
    screenshot: Path
    duration_ms: int


@dataclass(frozen=True)
class Storyboard:
    source: Path
    title: str
    tagline: str
    cta: str
    project_url: str
    demo: bool
    scenes: tuple[Scene, ...]

    @property
    def duration_ms(self) -> int:
        return sum(scene.duration_ms for scene in self.scenes)


def _text(obj: dict, field: str, limit: int, *, optional: bool = False) -> str:
    value = obj.get(field, "" if optional else None)
    if not isinstance(value, str) or (not optional and not value.strip()):
        raise StoryError(f"'{field}' must be a non-empty string")
    value = value.strip()
    if len(value) > limit:
        raise StoryError(f"'{field}' exceeds {limit} characters")
    if any(ord(char) < 32 for char in value):
        raise StoryError(f"'{field}' must not contain control characters")
    return value


def load_storyboard(path: Path) -> Storyboard:
    path = path.resolve()
    if not path.is_file():
        raise StoryError(f"Storyboard does not exist: {path}")
    if path.stat().st_size > 1_048_576:
        raise StoryError("Storyboard exceeds 1 MiB")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StoryError(f"Cannot read storyboard JSON: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != 1:
        raise StoryError("Storyboard must be an object with 'version': 1")
    if not isinstance(data.get("demo"), bool):
        raise StoryError("'demo' must explicitly be true or false")
    project_url = _text(data, "project_url", 200, optional=True)
    if project_url and not project_url.startswith(("https://", "http://")):
        raise StoryError("'project_url' must be an http(s) URL or empty")
    raw_scenes = data.get("scenes")
    if not isinstance(raw_scenes, list) or not 1 <= len(raw_scenes) <= 12:
        raise StoryError("'scenes' must contain 1 to 12 scenes")
    scenes = []
    for index, raw in enumerate(raw_scenes, 1):
        if not isinstance(raw, dict):
            raise StoryError(f"Scene {index} must be an object")
        try:
            name = _text(raw, "screenshot", 240)
            relative = Path(name)
            image_path = (path.parent / relative).resolve()
            if relative.is_absolute() or not image_path.is_relative_to(path.parent):
                raise StoryError("'screenshot' must stay inside the storyboard directory")
            if image_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                raise StoryError("'screenshot' must be PNG, JPEG or WebP")
            if not image_path.is_file():
                raise StoryError(f"Screenshot not found: {name}")
            try:
                with Image.open(image_path) as image:
                    if image.width * image.height > 30_000_000:
                        raise StoryError("Screenshot exceeds 30 megapixels")
                    if min(image.size) < 64:
                        raise StoryError("Screenshot must be at least 64 pixels on both sides")
                    image.verify()
            except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
                raise StoryError(f"Invalid screenshot: {name}") from exc
            duration = raw.get("duration")
            if isinstance(duration, bool) or not isinstance(duration, (float, int)):
                raise StoryError("'duration' must be a number of seconds")
            if not 2 <= duration <= 30 or not math.isfinite(duration):
                raise StoryError("'duration' must be between 2 and 30 seconds")
            scenes.append(Scene(
                _text(raw, "headline", 32),
                _text(raw, "detail", 80),
                _text(raw, "narration", 80),
                image_path,
                round(duration * 1000),
            ))
        except StoryError as exc:
            raise StoryError(f"Scene {index}: {exc}") from exc
    if sum(scene.duration_ms for scene in scenes) > 180_000:
        raise StoryError("Total duration must not exceed 180 seconds")
    return Storyboard(
        path, _text(data, "title", 32), _text(data, "tagline", 60),
        _text(data, "cta", 32), project_url, data["demo"], tuple(scenes),
    )
