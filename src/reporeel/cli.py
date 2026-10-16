"""Offline command-line interface."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

import PIL

from . import __version__
from .build import build, create_sample, discover_ffmpeg
from .model import StoryError
from .render import find_font


def doctor(ffmpeg: str | None, font: str | None) -> dict:
    result = {"reporeel": __version__, "python": sys.version.split()[0], "pillow": PIL.__version__, "font": None, "ffmpeg": None, "h264_encoder": False}
    try:
        result["font"] = str(find_font(font))
    except StoryError as exc:
        result["font_error"] = str(exc)
    executable = discover_ffmpeg(ffmpeg)
    if executable:
        result["ffmpeg"] = executable
        try:
            check = subprocess.run([executable, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=15, check=False)
            result["h264_encoder"] = check.returncode == 0 and "libx264" in check.stdout
        except (OSError, subprocess.TimeoutExpired) as exc:
            result["ffmpeg_error"] = str(exc)
    result["images_ready"] = bool(result["font"])
    result["video_ready"] = bool(result["font"] and result["h264_encoder"])
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="reporeel", description="Local screenshot → vertical project demo. No accounts, no API keys.")
    parser.add_argument("--version", action="version", version=f"RepoReel {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sample = sub.add_parser("sample", help="Create a clearly labelled DEMO storyboard and 3 synthetic screenshots")
    sample.add_argument("directory", type=Path)
    sample.add_argument("--font", help="CJK-capable TTF/TTC/OTF file")
    make = sub.add_parser("build", help="Render cover, frames, captions, scripts, manifest and silent MP4")
    make.add_argument("storyboard", type=Path)
    make.add_argument("--out", required=True, type=Path, help="New or empty output directory")
    make.add_argument("--ffmpeg", help="FFmpeg executable path (or set REPOREEL_FFMPEG)")
    make.add_argument("--font", help="CJK-capable font file (or set REPOREEL_FONT)")
    make.add_argument("--images-only", action="store_true", help="Generate all static assets and scripts; intentionally omit MP4")
    check = sub.add_parser("doctor", help="Inspect dependencies and H.264 encoding support")
    check.add_argument("--ffmpeg")
    check.add_argument("--font")
    args = parser.parse_args(argv)
    try:
        if args.command == "sample":
            path = create_sample(args.directory.resolve(), args.font)
            print(f"DEMO storyboard created: {path}")
        elif args.command == "doctor":
            status = doctor(args.ffmpeg, args.font)
            print(json.dumps(status, ensure_ascii=False, indent=2))
            return 0 if status["video_ready"] else 1
        else:
            manifest = build(args.storyboard, args.out, ffmpeg=args.ffmpeg, font=args.font, images_only=args.images_only)
            mode = "PNG assets + scripts (no video requested)" if args.images_only else "Silent H.264 MP4 + PNG assets + scripts"
            print(f"{mode}\nOutput: {args.out.resolve()}\nDuration: {manifest['duration_seconds']:g}s\nSource hashes: manifest.json")
        return 0
    except (StoryError, OSError, ValueError) as exc:
        print(f"reporeel: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
