"""Deterministic local artifacts and subprocess-based video encoding."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from . import __version__
from .model import Storyboard, StoryError, load_storyboard
from .render import Painter, create_demo_screenshot, find_font


def discover_ffmpeg(explicit: str | None = None) -> str | None:
    value = explicit or os.environ.get("REPOREEL_FFMPEG") or "ffmpeg"
    found = shutil.which(value)
    return str(Path(found).resolve()) if found else None


def timestamp(ms: int) -> str:
    hours, rest = divmod(ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def subtitles(story: Storyboard) -> str:
    parts, start = [], 0
    for index, scene in enumerate(story.scenes, 1):
        end = start + scene.duration_ms
        # A readable CJK-friendly cue; the full script is preserved in voiceover.txt.
        lines = [scene.narration[i:i+22] for i in range(0, len(scene.narration), 22)]
        parts.append(f"{index}\n{timestamp(start)} --> {timestamp(end)}\n" + "\n".join(lines))
        start = end
    return "\n\n".join(parts) + "\n"


def require_empty_directory(path: Path):
    if path.exists():
        if not path.is_dir() or any(path.iterdir()):
            raise StoryError(f"Output must be a new or empty directory: {path}")
    else:
        path.mkdir(parents=True)


def create_sample(directory: Path, font_path: str | None = None) -> Path:
    painter = Painter(find_font(font_path))
    require_empty_directory(directory)
    assets = directory / "assets"
    assets.mkdir()
    for i in range(1, 4):
        create_demo_screenshot(assets / f"demo-{i:02d}.png", i, painter)
    data = {
        "version": 1,
        "demo": True,
        "title": "把项目截图，变成演示视频",
        "tagline": "RepoReel / 一个本地运行的开源素材工具",
        "cta": "看制作过程，试试你自己的项目",
        "project_url": "",
        "scenes": [
            {"headline": "项目做出来了，怎么让人看懂？", "detail": "用你自己的项目截图，先把核心价值讲清楚。", "narration": "准备三张截图，把你的项目讲成一个短故事。", "screenshot": "assets/demo-01.png", "duration": 6},
            {"headline": "一句钩子，三个清晰步骤", "detail": "写好功能点和旁白，再把每一步交给模板。", "narration": "写下钩子、过程和行动提示，不用接付费接口。", "screenshot": "assets/demo-02.png", "duration": 6},
            {"headline": "导出视频，也保留原始素材", "detail": "竖屏画面、封面、字幕和文案一次整理好。", "narration": "视频默认静音。配音稿、字幕和素材清单一起交付。", "screenshot": "assets/demo-03.png", "duration": 6},
        ],
    }
    path = directory / "storyboard.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _publish_text(story: Storyboard) -> str:
    disclosure = "DEMO 模板示例；截图为自生成示意界面，不是客户案例或真实业绩。\n\n" if story.demo else "项目演示；请确认你拥有截图和内容的发布权。\n\n"
    link = story.project_url or "[待填写：真实项目地址；发布前替换]"
    bullets = "\n".join(f"- {scene.headline}：{scene.detail}" for scene in story.scenes)
    return (
        f"# 发布素材草稿\n\n{disclosure}"
        f"## 标题\n\n{story.title}\n\n"
        f"## 正文\n\n{story.tagline}\n\n{bullets}\n\n{story.cta}\n\n"
        f"项目地址：{link}\n\n"
        "#AI工具 #开源项目 #独立开发 #项目演示\n\n"
        "## 交付说明\n\n视频为静音画面；voiceover.txt 是待录制的旁白稿，captions.srt 是字幕。\n"
        "发布前核对事实、链接、字幕时长与平台展示效果；本工具不登录或发布。\n"
    )


def encode_video(ffmpeg: str, output: Path, story: Storyboard):
    timeline = []
    for index, scene in enumerate(story.scenes, 1):
        # All concat inputs are tool-generated ASCII names, never user expressions.
        timeline += [f"file 'frames/scene-{index:02d}.png'", f"duration {scene.duration_ms/1000:.3f}"]
    timeline.append(f"file 'frames/scene-{len(story.scenes):02d}.png'")
    (output/"timeline.ffconcat").write_text("ffconcat version 1.0\n"+"\n".join(timeline)+"\n", encoding="ascii")
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
        "-f", "concat", "-safe", "1", "-i", "timeline.ffconcat",
        "-frames:v", str(round(story.duration_ms*30/1000)), "-r", "30", "-pix_fmt", "yuv420p",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-movflags", "+faststart", "reel.mp4",
    ]
    try:
        result = subprocess.run(command, cwd=output, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StoryError(f"FFmpeg could not finish: {exc}. PNGs and scripts remain available.") from exc
    if result.returncode:
        raise StoryError(f"FFmpeg failed ({result.returncode}): {result.stderr[-4000:]}")
    video = output/"reel.mp4"
    if not video.is_file() or video.stat().st_size < 1024:
        raise StoryError("FFmpeg produced no usable video")
    with video.open("rb") as stream:
        if stream.read(12)[4:8] != b"ftyp":
            raise StoryError("Output does not contain an MP4 file header")


def build(storyboard: Path, output: Path, *, ffmpeg: str | None = None, font: str | None = None, images_only: bool = False) -> dict:
    story = load_storyboard(storyboard)
    painter = Painter(find_font(font))
    encoder = None if images_only else discover_ffmpeg(ffmpeg)
    if not images_only and not encoder:
        raise StoryError("FFmpeg not found. Pass --ffmpeg /path/to/ffmpeg, set REPOREEL_FFMPEG, or use --images-only")
    output = output.resolve()
    # Never write into the input tree: output must not overwrite or swallow source assets.
    if output == story.source.parent or story.source.is_relative_to(output):
        raise StoryError("Output must be separate from the storyboard directory and its parents")
    require_empty_directory(output)
    (output/"frames").mkdir()
    painter.cover(story).save(output/"cover.png")
    for index in range(len(story.scenes)):
        painter.scene(story, index).save(output/"frames"/f"scene-{index+1:02d}.png")
    (output/"captions.srt").write_text(subtitles(story), encoding="utf-8")
    script = ["旁白稿（待录制；导出视频无音轨）", "DEMO 模板示例" if story.demo else "项目演示", ""]
    elapsed = 0
    for index, scene in enumerate(story.scenes, 1):
        script += [f"{index:02d} | {elapsed/1000:.3f}–{(elapsed+scene.duration_ms)/1000:.3f}s", scene.narration, ""]
        elapsed += scene.duration_ms
    (output/"voiceover.txt").write_text("\n".join(script), encoding="utf-8")
    (output/"publish.md").write_text(_publish_text(story), encoding="utf-8")
    if encoder:
        encode_video(encoder, output, story)
    sources = [story.source, *sorted({scene.screenshot for scene in story.scenes})]
    manifest = {
        "schema_version": 1,
        "generator": f"RepoReel {__version__}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "demo": story.demo,
        "dimensions": [1080, 1920],
        "duration_seconds": round(story.duration_ms*30/1000)/30 if encoder else story.duration_ms/1000,
        "storyboard_duration_seconds": story.duration_ms/1000,
        "video": "reel.mp4" if encoder else None,
        "audio": "none; voiceover script supplied for recording",
        "sources": [{"path": path.relative_to(story.source.parent).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in sources],
        "artifacts": [{"path": path.relative_to(output).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in sorted(output.rglob("*")) if path.is_file()],
    }
    (output/"manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return manifest
