"""Optional real-encoder integration check, independent of the unit suite."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image, ImageChops, ImageStat

from reporeel.build import discover_ffmpeg
from reporeel.model import load_storyboard


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("storyboard", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    ffmpeg = discover_ffmpeg(args.ffmpeg)
    ffprobe = shutil.which(args.ffprobe)
    if not ffmpeg or not ffprobe:
        parser.error("Both FFmpeg and FFprobe must be available")
    ffprobe = str(Path(ffprobe).resolve())
    story = load_storyboard(args.storyboard)
    output = args.output.resolve()
    report = json.loads(subprocess.check_output([
        ffprobe, "-v", "error", "-show_entries",
        "stream=codec_name,codec_type,width,height,r_frame_rate,nb_frames:format=duration,size",
        "-of", "json", str(output/"reel.mp4"),
    ], text=True))
    streams = report["streams"]
    assert len(streams) == 1 and streams[0]["codec_type"] == "video", "Expected silent video only"
    assert streams[0]["codec_name"] == "h264"
    assert (streams[0]["width"], streams[0]["height"]) == (1080, 1920)
    assert streams[0]["r_frame_rate"] == "30/1"
    assert int(streams[0]["nb_frames"]) == round(story.duration_ms*30/1000)
    assert abs(float(report["format"]["duration"])-round(story.duration_ms*30/1000)/30) < 0.002
    checks, elapsed = [], 0
    with tempfile.TemporaryDirectory(prefix="reporeel-verify-") as scratch:
        for index, scene in enumerate(story.scenes, 1):
            second = (elapsed+scene.duration_ms/2)/1000
            elapsed += scene.duration_ms
            decoded = Path(scratch)/f"scene-{index:02d}.png"
            subprocess.run([
                ffmpeg, "-v", "error", "-nostdin", "-ss", str(second), "-i",
                str(output/"reel.mp4"), "-frames:v", "1", "-n", str(decoded),
            ], check=True, capture_output=True)
            with Image.open(decoded) as actual, Image.open(output/"frames"/f"scene-{index:02d}.png") as expected:
                difference = ImageChops.difference(actual.convert("RGB"), expected.convert("RGB"))
                error = max(ImageStat.Stat(difference).mean)
            assert error < 3, f"Scene {index} mismatched: mean channel error {error}"
            checks.append({"second": second, "expected_scene": index, "max_channel_mean_error": round(error, 4)})
    report["decoded_scene_checks"] = checks
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(rendered+"\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
