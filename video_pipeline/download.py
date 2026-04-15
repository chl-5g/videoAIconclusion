"""使用 yt-dlp 从哔哩哔哩等站点下载视频到本地目录（需已安装 ffmpeg 以便合并音视频流）。"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yt_dlp


def is_http_url(s: str) -> bool:
    t = s.strip().lower()
    return t.startswith("http://") or t.startswith("https://")


def _guess_bvid(url: str) -> str | None:
    m = re.search(r"(BV[0-9A-Za-z]+)", url, re.IGNORECASE)
    return m.group(1) if m else None


_illegal_re = re.compile(r'[\x00-\x1f<>:"|?*\\/]+')


def sanitize_job_name(raw: str, fallback: str) -> str:
    """用作目录名与文件前缀：去掉路径非法字符，空白改为下划线，过长截断。"""
    s = (raw or "").strip()
    s = re.sub(r"\s+", "_", s)
    s = _illegal_re.sub("_", s)
    s = re.sub(r"_+", "_", s).strip("_. ")
    if not s:
        s = (fallback or "video").strip()
        s = _illegal_re.sub("_", s)
    if len(s) > 120:
        s = s[:120].rstrip("._ ")
    return s or "video"


def extract_video_info(url: str) -> dict[str, str]:
    """不下载，仅解析页面，得到 id、title 等用于命名。"""
    opts: dict = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url.strip(), download=False)
    if not info:
        return {"id": "video", "title": "video"}
    if "entries" in info and info["entries"]:
        first = info["entries"][0] or {}
        vid = str(first.get("id") or info.get("id") or "video")
        title = str(first.get("title") or first.get("id") or vid)
        return {"id": vid, "title": title}
    vid = str(info.get("id") or "video")
    title = str(info.get("title") or info.get("id") or vid)
    return {"id": vid, "title": title}


def download_video_url(url: str, out_dir: Path, job_name: str) -> Path:
    """
    下载单个视频页面，写入 ``out_dir / f"{job_name}.mp4"``（或 yt-dlp 合并后的扩展名）。
    job_name 不含扩展名，需已通过 sanitize_job_name。
    """
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    last_file: list[str | None] = [None]

    def hook(d: dict) -> None:
        if d.get("status") == "finished" and d.get("filename"):
            last_file[0] = d["filename"]

    outtmpl = str(out_dir / f"{job_name}.%(ext)s")
    opts: dict = {
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "progress_hooks": [hook],
    }
    cookies = os.environ.get("YTDLP_COOKIEFILE")
    if cookies:
        opts["cookiefile"] = cookies

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url.strip()])

    if last_file[0]:
        p = Path(last_file[0])
        if p.is_file():
            return p

    for ext in ("mp4", "mkv", "webm", "flv"):
        p = out_dir / f"{job_name}.{ext}"
        if p.is_file():
            return p

    bvid = _guess_bvid(url)
    if bvid:
        for ext in ("mp4", "mkv", "webm", "flv"):
            p = out_dir / f"{bvid}.{ext}"
            if p.is_file():
                return p

    raise RuntimeError("下载结束但未找到输出文件，请检查 yt-dlp 日志与输出目录权限。")
