"""使用抖音移动端 API 下载视频（无水印，无需 cookie）。"""

from __future__ import annotations

import json
import logging
import time
import re
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

DOUYIN_DOMAIN_RE = re.compile(r"(?:v\.|www\.)?douyin\.com", re.IGNORECASE)
VIDEO_ID_RE = re.compile(r"/video/(\d{19})")
MODAL_ID_RE = re.compile(r"modal_id=(\d{19})")

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
)
ANDROID_UA = (
    "Mozilla/5.0 (Linux; Android 8.0.0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/86.0.4240.198 Mobile Safari/537.36"
)


def is_douyin_url(url: str) -> bool:
    """检测是否为抖音链接（短链或完整链接）。"""
    return bool(DOUYIN_DOMAIN_RE.search(url))


def _follow_redirect(url: str) -> str:
    """跟随短链重定向，返回真实 URL。"""
    r = requests.get(url.strip(), headers={"User-Agent": MOBILE_UA}, allow_redirects=True, timeout=15)
    return r.url


def _extract_video_id(url: str) -> str | None:
    """从 URL 中提取 19 位视频 ID。"""
    m = VIDEO_ID_RE.search(url) or MODAL_ID_RE.search(url)
    return m.group(1) if m else None


def _extract_video_json(html: str) -> dict:
    """从 iesdouyin 分享页 HTML 中提取 _ROUTER_DATA JSON。"""
    start = html.find("window._ROUTER_DATA")
    if start == -1:
        raise RuntimeError("页面中未找到 _ROUTER_DATA")

    json_start = html.find("{", start)
    if json_start == -1:
        raise RuntimeError("_ROUTER_DATA 后未找到 JSON 起始位置")

    depth = 0
    for i in range(json_start, len(html)):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(html[json_start : i + 1])

    raise RuntimeError("无法闭合 _ROUTER_DATA JSON")


def _find_video_item(data: dict) -> dict:
    """从 _ROUTER_DATA 中提取视频 item。"""
    ld = data.get("loaderData", {})
    page_key = next((k for k in ld if "video" in k and "page" in k), None)
    if not page_key:
        raise RuntimeError(f"找不到视频页面数据，loaderData 键: {list(ld.keys())}")

    page = ld[page_key]
    if not isinstance(page, dict):
        raise RuntimeError(f"页面数据类型异常: {type(page)}")

    video_info = page.get("videoInfoRes")
    if not video_info:
        raise RuntimeError("页面中未找到 videoInfoRes")

    item_list = video_info.get("item_list", [])
    if not item_list:
        raise RuntimeError("item_list 为空")

    return item_list[0]


def _get_download_uri(item: dict) -> str:
    """从视频 item 中提取无水印播放 URI。"""
    video = item.get("video")
    if not video:
        raise RuntimeError("item 中缺少 video 字段")

    play = video.get("play_addr")
    if not play:
        raise RuntimeError("video 中缺少 play_addr")

    uri = play.get("uri")
    if uri:
        return uri

    # fallback: url_list
    url_list = play.get("url_list", [])
    if url_list:
        return url_list[0]

    raise RuntimeError(f"无法提取视频 URI，play_addr 键: {list(play.keys())}")


def extract_douyin_video_info(url: str) -> dict[str, str]:
    """解析抖音页面，获取视频 id 和标题。"""
    logger.info("解析抖音视频信息：%s", url.strip())

    if "v.douyin.com" in url.lower():
        url = _follow_redirect(url)
        logger.info("重定向至：%s", url)

    vid = _extract_video_id(url)
    if not vid:
        raise RuntimeError(f"无法从 URL 提取视频 ID: {url}")

    api_url = f"https://www.iesdouyin.com/share/video/{vid}/"
    r = requests.get(api_url, headers={"User-Agent": ANDROID_UA, "Referer": "https://www.douyin.com/"}, timeout=15)
    r.raise_for_status()

    data = _extract_video_json(r.text)
    item = _find_video_item(data)

    title = (item.get("desc") or vid).strip()
    author = (item.get("author") or {}).get("nickname", "")

    return {"id": vid, "title": title, "author": author}


def download_douyin_video(url: str, out_dir: Path, job_name: str) -> Path:
    """下载抖音视频到 ``out_dir / f"{job_name}.mp4"``。"""
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info("下载抖音视频：%s", url.strip())
    logger.info("输出目录：%s", out_dir)

    if "v.douyin.com" in url.lower():
        url = _follow_redirect(url)

    vid = _extract_video_id(url)
    if not vid:
        raise RuntimeError(f"无法从 URL 提取视频 ID: {url}")

    api_url = f"https://www.iesdouyin.com/share/video/{vid}/"
    r = requests.get(api_url, headers={"User-Agent": ANDROID_UA, "Referer": "https://www.douyin.com/"}, timeout=15)
    r.raise_for_status()

    data = _extract_video_json(r.text)
    item = _find_video_item(data)
    uri = _get_download_uri(item)

    dl_url = f"https://www.douyin.com/aweme/v1/play/?video_id={uri}"
    logger.info("下载地址已解析，开始传输...")

    out_path = out_dir / f"{job_name}.mp4"
    _download_with_retry(dl_url, out_path)

    size_mb = out_path.stat().st_size / (1024 * 1024)
    logger.info("下载完成：%s (%.1f MB)", out_path, size_mb)
    return out_path


def _download_with_retry(url: str, out_path: Path, max_retries: int = 3) -> None:
    """下载文件，失败时自动重试。"""
    headers = {"User-Agent": MOBILE_UA, "Referer": "https://www.douyin.com/"}
    for attempt in range(max_retries):
        try:
            with requests.get(url, headers=headers, stream=True, timeout=(10, 120)) as r:
                r.raise_for_status()
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
            return
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 2
                logger.warning("下载中断（%s），%ds 后重试 (%d/%d)...", e, wait, attempt + 2, max_retries)
                time.sleep(wait)
            else:
                raise RuntimeError(f"下载失败，已重试 {max_retries} 次: {e}") from e
