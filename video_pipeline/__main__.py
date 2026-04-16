"""CLI：视频 → WAV → 转写 →（可选）大模型总结。"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from video_pipeline.download import (
    download_video_url,
    extract_video_info,
    is_http_url,
    sanitize_job_name,
)
from video_pipeline.extract import extract_wav_16k_mono
from video_pipeline.summarize import summarize_transcript
from video_pipeline.transcribe import (
    segments_simplified_chinese,
    segments_to_plain_text,
    transcribe_audio,
)


def main() -> int:
    p = argparse.ArgumentParser(description="视频流水线：FFmpeg 抽音频 → Faster-Whisper → LLM 总结")
    p.add_argument(
        "video",
        type=str,
        metavar="PATH_OR_URL",
        help="本地视频路径，或 https:// 开头的页面链接（如哔哩哔哩）",
    )
    p.add_argument(
        "-o",
        "--out",
        type=Path,
        default=None,
        help="工作目录；省略时自动为 ./output/<视频名>/（链接用页面标题生成视频名）",
    )
    p.add_argument("--whisper-model", default="small", help="Whisper 模型：tiny/base/small/medium/large-v3 等")
    p.add_argument("--device", default="cpu", help="推理设备：cpu 或 cuda")
    p.add_argument(
        "--compute-type",
        default="int8",
        help="faster-whisper compute_type：CPU 常用 int8；CUDA 可试 float16",
    )
    p.add_argument(
        "--language",
        default="zh",
        help="转写语言：默认 zh（中文）；填 auto 为自动检测；可填 en 等",
    )
    p.add_argument("--skip-summary", action="store_true", help="只做转写，不调用 LLM")
    p.add_argument("--max-chars", type=int, default=120_000, help="送入 LLM 的逐字稿最大字符数（防止超长）")
    args = p.parse_args()

    raw_input = (args.video or "").strip()
    cwd = Path.cwd()

    if is_http_url(raw_input):
        meta = extract_video_info(raw_input)
        default_name = sanitize_job_name(meta["title"], meta["id"])
        if args.out is not None:
            out_dir = args.out.expanduser().resolve()
            job_name = out_dir.name
        else:
            job_name = default_name
            out_dir = (cwd / "output" / job_name).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        print("[0] 从链接下载视频（yt-dlp）…")
        video = download_video_url(raw_input, out_dir, job_name)
        print(f"      已保存：{video}")
    else:
        video = Path(raw_input).expanduser().resolve()
        if not video.is_file():
            print(f"文件不存在：{video}", file=sys.stderr)
            return 1
        default_name = sanitize_job_name(video.stem, video.stem)
        if args.out is not None:
            out_dir = args.out.expanduser().resolve()
            job_name = out_dir.name
        else:
            job_name = default_name
            out_dir = (cwd / "output" / job_name).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

    wav_path = out_dir / f"{job_name}.wav"

    print("[1/3] 提取音频（FFmpeg）…")
    extract_wav_16k_mono(video, wav_path)
    print(f"      已写入：{wav_path}")

    print("[2/3] 语音转文本（Faster-Whisper）…")
    raw_lang = (args.language or "").strip()
    lang: str | None = None if raw_lang.lower() == "auto" else (raw_lang or "zh")
    segments, detected = transcribe_audio(
        wav_path,
        model_size=args.whisper_model,
        device=args.device,
        compute_type=args.compute_type,
        language=lang,
    )
    print(f"      检测/使用语言：{detected}" + (f"（解码语言：{lang}）" if lang else "（解码语言：自动）"))

    if (lang and lang.lower() == "zh") or detected == "zh":
        segments = segments_simplified_chinese(segments)
        print("      已转为简体中文（UTF-8 文本）。")

    plain = segments_to_plain_text(segments)

    plain_no_ws = re.sub(r"\s+", "", plain)
    (out_dir / f"{job_name}.txt").write_text(plain_no_ws, encoding="utf-8")
    print(f"      已写入：{job_name}.txt（已去除空白字符）")

    if args.skip_summary or not os.environ.get("OPENAI_API_KEY"):
        if not args.skip_summary and not os.environ.get("OPENAI_API_KEY"):
            print("[3/3] 跳过总结：未设置环境变量 OPENAI_API_KEY。可加 --skip-summary 消除本提示。")
        else:
            print("[3/3] 已按参数跳过总结。")
        return 0

    print("[3/3] 生成总结（OpenAI 兼容 API）…")
    body = plain if len(plain) <= args.max_chars else plain[: args.max_chars] + "\n\n…（已截断，可调 --max-chars）"
    summary = summarize_transcript(body)
    conclusion_path = out_dir / f"{job_name}_conclusion.md"
    conclusion_path.write_text(summary, encoding="utf-8")
    print(f"      已写入：{conclusion_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
