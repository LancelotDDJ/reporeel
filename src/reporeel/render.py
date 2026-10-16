"""Pillow-only assets; usable without FFmpeg, accounts or API keys."""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .model import Storyboard, StoryError

WIDTH, HEIGHT = 1080, 1920
BG = "#111819"
SURFACE = "#1b2525"
INK = "#f4f2e9"
MUTED = "#b5c1ba"
ACCENT = "#dbfa76"


def find_font(explicit: str | None = None) -> Path:
    if explicit or os.environ.get("REPOREEL_FONT"):
        requested = Path(explicit or os.environ["REPOREEL_FONT"])
        if not requested.is_file():
            raise StoryError(f"Font not found: {requested}")
        return requested.resolve()
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return Path(candidate)
    raise StoryError("A CJK font is required. Install Noto Sans CJK or pass --font /path/to/font.ttf")


class Painter:
    def __init__(self, font_path: Path):
        self.font_path = font_path

    def font(self, size: int):
        return ImageFont.truetype(str(self.font_path), size=size)

    def wrap(self, draw, text: str, font, width: int) -> list[str]:
        lines, current = [], ""
        for char in text:
            candidate = current + char
            if current and draw.textlength(candidate, font=font) > width:
                lines.append(current.rstrip())
                current = char.lstrip()
            else:
                current = candidate
        if current:
            lines.append(current.rstrip())
        # Avoid a large Chinese headline ending in a lonely one-word second line.
        if len(lines) == 2 and len(lines[0]) > len(lines[1])*1.7:
            choices = []
            for split in range(1, len(text)):
                left, right = text[:split].rstrip(), text[split:].lstrip()
                left_width = draw.textlength(left, font=font)
                right_width = draw.textlength(right, font=font)
                if max(left_width, right_width) <= width:
                    penalty = abs(left_width-right_width)
                    if left[-1:] in "，。！？：、,!?;:":
                        penalty *= 0.55
                    choices.append((penalty, left, right))
            if choices:
                _, left, right = min(choices)
                lines = [left, right]
        return lines or [""]

    def text(self, draw, value, xy, *, size=48, width=936, lines=2, color=INK, gap=18):
        # Fit rather than silently losing meaningful words.
        while size >= 20:
            font = self.font(size)
            wrapped = self.wrap(draw, value, font, width)
            if len(wrapped) <= lines:
                break
            size -= 2
        if len(wrapped) > lines:
            raise StoryError(f"Text cannot fit this layout: {value[:30]}")
        x, y = xy
        for line in wrapped:
            draw.text((x, y), line, fill=color, font=font, stroke_width=0)
            y += size + gap
        return y

    def base(self, demo: bool):
        image = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((72, 78, 120, 126), radius=13, fill=ACCENT)
        draw.polygon([(89, 89), (89, 115), (108, 102)], fill=BG)
        draw.text((139, 72), "RepoReel", font=self.font(38), fill=INK)
        label = "DEMO / 模板示例" if demo else "PROJECT DEMO"
        font = self.font(24)
        label_width = int(draw.textlength(label, font=font)) + 34
        draw.rounded_rectangle((1008-label_width, 83, 1008, 128), radius=22, outline="#52603f", width=2)
        draw.text((1025-label_width, 89), label, font=font, fill=ACCENT)
        draw.line((72, 164, 1008, 164), fill="#34403c", width=2)
        return image, draw

    def screenshot(self, image, path: Path, box):
        x0, y0, x1, y1 = box
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(box, radius=28, fill=SURFACE, outline="#3c4a42", width=2)
        draw.text((x0+28, y0+17), "●  ●  ●", font=self.font(19), fill="#849475")
        with Image.open(path) as source:
            source = ImageOps.exif_transpose(source).convert("RGB")
            contained = ImageOps.contain(source, (x1-x0-36, y1-y0-78), Image.Resampling.LANCZOS)
        image.paste(contained, (x0+(x1-x0-contained.width)//2, y0+58+(y1-y0-76-contained.height)//2))

    def scene(self, story: Storyboard, index: int) -> Image.Image:
        scene = story.scenes[index]
        image, draw = self.base(story.demo)
        draw.text((72, 213), f"BUILD IN PUBLIC     /     {index+1:02d}", font=self.font(26), fill=ACCENT)
        self.text(draw, scene.headline, (72, 285), size=76, lines=2)
        self.text(draw, scene.detail, (76, 516), size=36, lines=3, color=MUTED, gap=14)
        self.screenshot(image, scene.screenshot, (72, 730, 1008, 1430))
        draw.rounded_rectangle((72, 1484, 1008, 1640), radius=22, fill=ACCENT)
        self.text(draw, scene.narration, (103, 1511), size=35, width=874, lines=2, color=BG, gap=10)
        self.text(draw, story.cta, (72, 1690), size=39, width=936, lines=2)
        draw.text((72, 1800), story.title, font=self.font(25), fill=MUTED)
        draw.text((900, 1800), f"{index+1}/{len(story.scenes)}", font=self.font(25), fill=MUTED)
        segment_width = 920 / len(story.scenes)
        for i in range(len(story.scenes)):
            x = 72+round(segment_width*i)
            draw.rounded_rectangle((x, 1861, x+round(segment_width)-10, 1867), radius=3, fill=ACCENT if i<=index else "#3c4a42")
        return image

    def cover(self, story: Storyboard) -> Image.Image:
        image, draw = self.base(story.demo)
        draw.text((72, 225), "SCREENSHOTS → VERTICAL VIDEO", font=self.font(27), fill=ACCENT)
        self.text(draw, story.title, (72, 320), size=92, lines=2, gap=25)
        self.text(draw, story.tagline, (76, 615), size=43, lines=2, color=MUTED, gap=16)
        self.screenshot(image, story.scenes[0].screenshot, (72, 865, 1008, 1535))
        draw.rounded_rectangle((72, 1620, 1008, 1760), radius=25, fill=ACCENT)
        self.text(draw, story.cta, (108, 1653), size=42, width=860, lines=1, color=BG)
        draw.text((72, 1830), "LOCAL EXPORT   /   NO API KEY", font=self.font(24), fill=MUTED)
        return image


def create_demo_screenshot(path: Path, number: int, painter: Painter):
    """Synthetic UI, deliberately labelled as a template, never customer evidence."""
    image = Image.new("RGB", (1440, 940), "#f1f0e8")
    d = ImageDraw.Draw(image)
    d.rectangle((0, 0, 1440, 94), fill="#16201d")
    d.text((42, 23), "REPOREEL  /  DEMO 模板界面", font=painter.font(33), fill="#e0fa87")
    d.text((56, 136), ["01 / 导入项目截图", "02 / 整理你的故事", "03 / 本地导出素材"][number-1], font=painter.font(46), fill="#16201d")
    d.text((58, 215), "示意图 · 非真实产品数据 · 不代表实际用户或收入", font=painter.font(26), fill="#586055")
    if number == 1:
        for i, label in enumerate(["项目首页.png", "核心功能.png", "操作过程.png"]):
            x = 56+i*438
            d.rounded_rectangle((x, 312, x+410, 765), radius=20, fill="#dfe4d6", outline="#aebca4", width=2)
            d.rounded_rectangle((x+23, 345, x+387, 620), radius=12, fill=["#ceddb2", "#e4d4bb", "#c6d9d8"][i])
            d.text((x+44, 431), f"DEMO {i+1:02d}", font=painter.font(45), fill="#243225")
            d.text((x+25, 673), label, font=painter.font(29), fill="#243225")
    elif number == 2:
        for i, label in enumerate(["钩子：截图也能讲清项目", "过程：功能点 + 旁白 + 时长", "行动：去试用 / 看源码"]):
            y=312+i*153
            d.rounded_rectangle((56,y,1384,y+126), radius=17, fill="#e0e6d8")
            d.text((85,y+35),label,font=painter.font(35),fill="#243225")
    else:
        d.rounded_rectangle((56,312,1384,780),radius=20,fill="#e0e6d8")
        for i, label in enumerate(["cover.png", "reel.mp4  /  1080 × 1920", "captions.srt + voiceover.txt", "publish.md + manifest.json"]):
            d.text((95,350+i*94),label,font=painter.font(35),fill="#243225")
    d.text((56, 851), "DEMO ONLY   /   自生成示意素材", font=painter.font(25), fill="#596650")
    image.save(path)
