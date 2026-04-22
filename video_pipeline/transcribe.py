"""Faster-Whisper 转写，输出带时间戳的片段。"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

import zhconv
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


@dataclass
class Segment:
    start: float
    end: float
    text: str


def to_simplified_chinese(text: str) -> str:
    """将中文统一为大陆常用字形（UTF-8 下存储的 Unicode 字符）。"""
    return zhconv.convert(text, "zh-cn")


def segments_simplified_chinese(segments: list[Segment]) -> list[Segment]:
    return [Segment(s.start, s.end, to_simplified_chinese(s.text)) for s in segments]


def transcribe_audio(
    wav_path: Path,
    model_size: str = "small",
    device: str = "cpu",
    compute_type: str = "int8",
    language: str | None = None,
) -> tuple[list[Segment], str]:
    """
    language: None 表示自动检测；传 'zh' 则按中文解码（更适合出简体主导文本）。
    compute_type: CPU 推荐 int8；有 NVIDIA GPU 可试 float16。
    """
    logger.info(
        "加载 Whisper 模型：model=%s device=%s compute_type=%s language=%s",
        model_size,
        device,
        compute_type,
        language or "auto",
    )
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    logger.info("开始转写音频：%s", wav_path)
    segments_iter, info = model.transcribe(
        str(wav_path),
        language=language,
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
        hallucination_silence_threshold=2.0,
    )
    segments: list[Segment] = []
    for seg in segments_iter:
        segments.append(Segment(start=seg.start, end=seg.end, text=seg.text.strip()))
    detected = info.language or "unknown"
    logger.info("转写完成：segments=%d detected_language=%s", len(segments), detected)
    return segments, detected


def segments_to_plain_text(segments: list[Segment]) -> str:
    return " ".join(s.text for s in segments if s.text).strip()


def segments_to_timestamped_text(segments: list[Segment]) -> str:
    lines = []
    for s in segments:
        if not s.text:
            continue
        lines.append(f"[{s.start:.1f}s - {s.end:.1f}s] {s.text}")
    return "\n".join(lines)
