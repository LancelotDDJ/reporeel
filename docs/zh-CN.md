# RepoReel 中文说明

把自己的项目截图和功能点，整理成中文竖屏演示视频与发布素材。先把项目讲清楚，再用真实发布结果验证是否有人需要。

首版完全本地运行，只依赖 Python、Pillow 和可选的 FFmpeg。没有登录、付费接口、自动发布或内置 AI 文案生成。示例脚本和界面都明确标为 **DEMO 模板示例**。

## 先看效果

[30 秒合成旁白 DEMO](https://github.com/LancelotDDJ/reporeel/releases/download/v0.1.0/reporeel-30s-a-publication.mp4) · [v0.1.0 预览版下载](https://github.com/LancelotDDJ/reporeel/releases/tag/v0.1.0)

样片另外添加了合成旁白，CLI 本身仍输出静音视频。演示制作于首次开源之前，片中的待公开说明为当时状态；当前源码与下载已公开。首版为预览版，暂无已验证的增长或收入效果。

## 开始运行

克隆后进入项目根目录。如果下载的是源码 ZIP，先解压，在含 `pyproject.toml` 的目录打开终端，并跳过下面前两行。

```powershell
git clone https://github.com/LancelotDDJ/reporeel.git
cd reporeel
python -m pip install -e .
python -m reporeel sample demo
python -m reporeel build demo/storyboard.json --out output/first-demo
```

需要 Python 3.10+。导出视频还需要含 `libx264` 编码器的 FFmpeg。用 `python -m reporeel doctor` 检查环境；FFmpeg 不在 PATH 时，通过 `--ffmpeg "路径/ffmpeg.exe"` 指定。

没有 FFmpeg 时，`doctor` 返回退出码 1，并显示 `video_ready: false`；这表示视频编码尚未就绪。如果 `images_ready` 为 `true`，图片与文案仍可生成，将视频导出命令换成：

```powershell
python -m reporeel build demo/storyboard.json --out output/stills --images-only
```

Windows 默认识别微软雅黑，macOS 识别苹方，Linux 识别常见路径的 Noto Sans CJK。也可以用 `--font` 指定支持中文的字体。字体及 FFmpeg 不随项目分发。

## 先做一条真实演示

1. 运行 `sample` 生成三张明确标为 DEMO 的示意图和 `storyboard.json`。
2. 用你有权使用的项目截图替换 `assets/` 中的图片。删除截图中的个人资料、密钥、私人对话和本地用户路径。
3. 编辑 JSON：用一句话钩子、清楚的操作过程和一个行动提示讲故事。字段含义见[英文 README](../README.md)。可自行撰写，也可交给外部 AI/Agent 起草后核对。
4. 填真实的项目链接；没有就留空，发布稿会保留明确的待填占位。只有内容已换成真实项目时，才把 `demo` 改为 `false`。
5. 导出后检查 `cover.png`、场景画面、`publish.md` 与 `manifest.json`。视频默认**静音**；`voiceover.txt` 是待录制旁白稿，`captions.srt` 是字幕文件。
6. 自己录音、发布与查看平台反馈；用实际粉丝、真实 GitHub Stars 和实际到账验证结果。本工具不提供增长或收入保证。

## 文件与约束

视频固定 1080×1920、30 fps、H.264 MP4，无音轨；每一幕为静态设计画面。实际总长取最近的 1/30 秒，清单同时保留请求的脚本时长。`--images-only` 明确只导出图片和文本，不会生成伪视频。

支持 1–12 幕，每幕 2–30 秒，总长不超过 180 秒。标题、行动提示和每幕标题最多 32 字符；副标题最多 60 字符；每幕说明及旁白最多 80 字符。保持简短能让手机端更易阅读。

截图路径必须位于 JSON 所在目录内，不能通过 `..` 或符号链接访问外部文件。支持 PNG/JPEG/WebP，最小 64×64，最大 3000 万像素。输出必须是新的或空目录，已有文件不会被覆盖；每次导出换一个目录。

`manifest.json` 保存输入 JSON、每张原图和输出文件的 SHA-256 与字节数，用于核对素材来源及完整性。它记录文件名，不写入本机绝对路径。哈希不等同于版权证明。

如 FFmpeg 失败，命令返回非零状态，已生成的图片和脚本保留。修正问题后使用新的输出目录重新运行。导出过程不会登录账号、发送内容或联网获取素材。

## 参与开发

```powershell
python -m unittest discover -s tests -v
```

欢迎提供可复现的问题、清晰的小改进与原创演示。协议为 MIT。
