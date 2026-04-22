"""用 FFmpeg 从视频提取 16kHz 单声道 WAV，供 Whisper 使用。"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        logger.error("未找到 ffmpeg 可执行文件。")
        raise RuntimeError(
            "未找到 ffmpeg。请先安装：brew install ffmpeg（macOS）或从 https://ffmpeg.org 获取。"
        )


def extract_wav_16k_mono(video_path: Path, out_wav: Path) -> Path:
    require_ffmpeg()
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    logger.info("开始提取音频：%s -> %s", video_path, out_wav)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(out_wav),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        logger.error("ffmpeg 执行失败：%s", r.stderr or r.stdout)
        raise RuntimeError(f"ffmpeg 失败：{r.stderr or r.stdout}")
    logger.info("音频提取完成：%s", out_wav)
    return out_wav
