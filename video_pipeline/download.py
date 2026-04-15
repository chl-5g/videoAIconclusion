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


def download_video_url(url: str, out_dir: Path) -> Path:
    """
    下载单个视频页面，返回磁盘上的媒体文件路径（优先 mp4）。
    输出模板：{视频 id}.%(ext)s，与 B 站 BV 号一致时便于后续命名。
    """
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    last_file: list[str | None] = [None]

    def hook(d: dict) -> None:
        if d.get("status") == "finished" and d.get("filename"):
            last_file[0] = d["filename"]

    outtmpl = str(out_dir / "%(id)s.%(ext)s")
    opts: dict = {
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "progress_hooks": [hook],
        # 会员清晰度、地区限制等可能需要 cookie，见 README
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

    bvid = _guess_bvid(url)
    if bvid:
        for ext in ("mp4", "mkv", "webm", "flv"):
            p = out_dir / f"{bvid}.{ext}"
            if p.is_file():
                return p

    raise RuntimeError("下载结束但未找到输出文件，请检查 yt-dlp 日志与输出目录权限。")
