import copy
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from reporeel.build import build, sha256, subtitles, timestamp
from reporeel.model import StoryError, load_storyboard
from reporeel.render import find_font


class StoryboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source_dir = self.root/"story"
        self.source_dir.mkdir()
        Image.new("RGB", (128, 96), "green").save(self.source_dir/"screen.png")
        self.path = self.source_dir/"storyboard.json"
        self.data = {
            "version": 1, "demo": True, "title": "中文项目演示", "tagline": "真实截图", "cta": "查看项目", "project_url": "",
            "scenes": [{"headline": "功能演示", "detail": "清楚讲功能", "narration": "看看这个功能", "screenshot": "screen.png", "duration": 2.125}],
        }
        self.write()

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")

    def test_fractional_timing_has_exact_contiguous_subtitles(self):
        self.data["scenes"].append({**self.data["scenes"][0], "duration": 3.25})
        self.write()
        story = load_storyboard(self.path)
        self.assertEqual(story.duration_ms, 5375)
        self.assertIn("00:00:00,000 --> 00:00:02,125", subtitles(story))
        self.assertIn("00:00:02,125 --> 00:00:05,375", subtitles(story))
        self.assertEqual(timestamp(3_661_123), "01:01:01,123")

    def test_path_escape_is_rejected(self):
        Image.new("RGB", (128, 96), "red").save(self.root/"private.png")
        for screenshot in ["../private.png", str((self.root/"private.png").resolve())]:
            with self.subTest(screenshot=screenshot):
                self.data["scenes"][0]["screenshot"] = screenshot
                self.write()
                with self.assertRaisesRegex(StoryError, "inside the storyboard directory"):
                    load_storyboard(self.path)

    def test_invalid_durations_and_missing_fields_are_rejected(self):
        original = copy.deepcopy(self.data)
        for duration in [True, 0, 31, 10**1000, float("nan"), "6"]:
            with self.subTest(duration=duration):
                self.data = copy.deepcopy(original)
                self.data["scenes"][0]["duration"] = duration
                self.write()
                with self.assertRaises(StoryError):
                    load_storyboard(self.path)
        self.data = original
        del self.data["title"]
        self.write()
        with self.assertRaisesRegex(StoryError, "title"):
            load_storyboard(self.path)

    def test_corrupt_image_is_rejected(self):
        (self.source_dir/"screen.png").write_bytes(b"not an image")
        with self.assertRaisesRegex(StoryError, "Invalid screenshot"):
            load_storyboard(self.path)

    def test_total_runtime_is_limited(self):
        self.data["scenes"] = [{**self.data["scenes"][0], "duration": 30} for _ in range(7)]
        self.write()
        with self.assertRaisesRegex(StoryError, "180 seconds"):
            load_storyboard(self.path)

    def test_demo_disclosure_must_be_explicit(self):
        del self.data["demo"]
        self.write()
        with self.assertRaisesRegex(StoryError, "explicitly"):
            load_storyboard(self.path)

    def _font_or_skip(self):
        try:
            return str(find_font())
        except StoryError:
            self.skipTest("Install a CJK font for rendering integration tests")

    def test_images_build_has_verified_source_manifest_and_real_dimensions(self):
        output = self.root/"export"
        manifest = build(self.path, output, font=self._font_or_skip(), images_only=True)
        self.assertIsNone(manifest["video"])
        self.assertFalse((output/"reel.mp4").exists())
        self.assertEqual(manifest["duration_seconds"], 2.125)
        for source in manifest["sources"]:
            self.assertEqual(source["sha256"], sha256(self.source_dir/source["path"]))
            self.assertFalse(Path(source["path"]).is_absolute())
        for item in manifest["artifacts"]:
            self.assertEqual(item["sha256"], sha256(output/item["path"]))
        for path in [output/"cover.png", output/"frames"/"scene-01.png"]:
            with Image.open(path) as image:
                self.assertEqual(image.size, (1080, 1920))
        self.assertIn("DEMO", (output/"publish.md").read_text(encoding="utf-8"))
        self.assertIn("待录制", (output/"voiceover.txt").read_text(encoding="utf-8"))

    def test_existing_output_and_source_directory_are_preserved(self):
        font = self._font_or_skip()
        output = self.root/"keep"
        output.mkdir()
        sentinel = output/"mine.txt"
        sentinel.write_text("keep me", encoding="utf-8")
        with self.assertRaisesRegex(StoryError, "new or empty"):
            build(self.path, output, font=font, images_only=True)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep me")
        with self.assertRaisesRegex(StoryError, "separate"):
            build(self.path, self.source_dir, font=font, images_only=True)

    def test_missing_ffmpeg_does_not_claim_success_or_create_output(self):
        output = self.root/"absent"
        with self.assertRaisesRegex(StoryError, "FFmpeg not found"):
            build(self.path, output, font=self._font_or_skip(), ffmpeg="not-a-real-ffmpeg-executable-784223")
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
