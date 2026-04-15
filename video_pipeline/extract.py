"""用 FFmpeg 从视频提取 16kHz 单声道 WAV，供 Whisper 使用。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "未找到 ffmpeg。请先安装：brew install ffmpeg（macOS）或从 https://ffmpeg.org 获取。"
        )


def extract_wav_16k_mono(video_path: Path, out_wav: Path) -> Path:
    require_ffmpeg()
    out_wav.parent.mkdir(parents=True, exist_ok=True)
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
        raise RuntimeError(f"ffmpeg 失败：{r.stderr or r.stdout}")
    return out_wav
