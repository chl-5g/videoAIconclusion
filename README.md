# videoAIconclusion

本地视频或 **网页链接**（如哔哩哔哩）的「可选下载 → 抽音频 → 语音转写 →（可选）大模型总结」流水线，组件可拆开替换：**yt-dlp**、FFmpeg、faster-whisper、任意 **OpenAI 兼容** Chat Completions 接口。

## 流程概览

0. **yt-dlp**（可选）：当第一个参数为 `http(s)://` 链接时，先把视频下载到 `-o` 指定目录（合并为 mp4 需本机 **ffmpeg**）。  
1. **FFmpeg**：从视频导出 16 kHz 单声道 PCM WAV，供 Whisper 使用。  
2. **Faster-Whisper**：转写为带时间戳的片段；默认按中文解码，并对中文结果做 **简体字形** 规范化（`zhconv`）。  
3. **HTTP API 总结（默认关闭）**：需加 `--summarize` 并配置 `OPENAI_API_KEY` 才会将全文逐字稿 POST 到 `/v1/chat/completions` 生成 `_conclusion.md`。默认只产出转写。

使用在线链接时，请自行遵守平台服务条款与版权法，仅处理你有权下载与转写的视频。

所有文本产物均为 **UTF-8** 编码写入磁盘。

## 环境要求

- **Python**：建议 3.10+（开发时在 3.12 上验证）。  
- **ffmpeg**：必须在 `PATH` 中可用（macOS 示例：`brew install ffmpeg`）。  
- **磁盘与网络**：首次运行会按所选模型从 Hugging Face 拉取 Whisper 权重（体积随模型增大）。

可选：NVIDIA GPU + CUDA 时可将 `--device cuda`，并酌情把 `--compute-type` 设为 `float16`。

## 安装

```bash
cd /path/to/videoAIconclusion
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

如需启用大模型总结（`--summarize`），复制环境变量模板并填写；不需要总结时可跳过：

```bash
cp env.example .env
# 编辑 .env；程序启动时会通过 python-dotenv 自动加载（若已安装）
```

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | 调用总结接口的密钥；仅转写时可不设。 |
| `OPENAI_BASE_URL` | 可选，默认 `https://api.openai.com/v1`。DeepSeek、自建网关、Ollama（`http://127.0.0.1:11434/v1`）等填对应前缀。 |
| `LLM_MODEL` | 可选，默认 `gpt-4o-mini`；例如 DeepSeek 可用 `deepseek-chat`。 |
| `YTDLP_COOKIEFILE` | 可选，Netscape 格式 cookie 文件路径；部分 B 站高码率或校验场景可能需要（见 `env.example`）。 |

## 命令行用法

在项目根目录执行（保证当前工作目录包含 `video_pipeline` 包）：

```bash
# 默认只做「下载 → 抽音频 → 转写」，不调用大模型总结
# 不写 -o 时：工作目录为 ./output/<视频名>/（链接用页面标题生成「视频名」，本地文件用文件名无后缀）
python -m video_pipeline /path/to/demo.mp4
```

使用哔哩哔哩等页面链接时，会先调用 `video_pipeline/download.py`（`extract_video_info` 命名 + `download_video_url` 下载），再走转写：

```bash
python -m video_pipeline "https://www.bilibili.com/video/BV173wdzgEFu/"
```

若希望目录名固定为 `aaa`（与视频文件前缀一致），可显式指定工作目录（取**最后一级目录名**作为「视频名」）：

```bash
python -m video_pipeline "https://..." -o ./output/aaa
# 产物示例：./output/aaa/aaa.mp4、./output/aaa/aaa.wav、./output/aaa/aaa.txt
```

如需顺带生成大模型总结：

```bash
python -m video_pipeline "https://..." --summarize
# 额外产出：./output/<视频名>/<视频名>_conclusion.md
```

常用参数：

| 参数 | 含义 |
|------|------|
| `-o`, `--out` | 工作目录；**省略**时为 `./output/<视频名>/`。传入 `./output/aaa` 时，视频名为 `aaa`。 |
| `--whisper-model` | `tiny` / `base` / `small` / `medium` / `large-v3` 等；机器较慢时优先减小模型。 |
| `--device` | `cpu`（默认）或 `cuda`。 |
| `--compute-type` | CPU 上常用 `int8`；CUDA 可试 `float16`。 |
| `--language` | 默认 `zh`（中文转写）；`auto` 为自动检测语言；也可显式指定 `en` 等。 |
| `--summarize` | **默认关闭**：加上才调用大模型生成 `_conclusion.md`；`summarize.py` 后端代码保留以便未来启用。 |
| `--max-chars` | 送入模型的逐字稿最大字符数，默认 `120000`，超出会截断并标注。 |

示例：

```bash
# 默认行为：仅转写，写入 ./output/demo/（demo 为文件名无后缀）
python -m video_pipeline ./demo.mp4

# 弱 CPU：更小模型
python -m video_pipeline ./demo.mp4 --whisper-model base

# 英文视频
python -m video_pipeline ./talk.mp4 --language en

# 额外跑大模型总结
python -m video_pipeline ./demo.mp4 --summarize
```

## 输出文件

设「视频名」为 `aaa`（即工作目录 `./output/aaa/` 的最后一级目录名），则同目录下约定如下（均为 UTF-8）：

| 文件 | 说明 | 触发条件 |
|------|------|------|
| `aaa.mp4` | 从链接下载时的视频文件（扩展名以 yt-dlp 合并结果为准，多为 mp4）。 | 输入为 URL |
| `aaa.wav` | 16 kHz 单声道音频（Whisper 输入）。 | 总是生成 |
| `aaa.txt` | 纯文本逐字稿，**已压掉所有空白字符**（空格/换行/制表）。 | 总是生成 |
| `aaa_conclusion.md` | 大模型 Markdown 总结。 | `--summarize` + `OPENAI_API_KEY` |

**本地视频**未使用 `-o` 时：不会复制原文件，仍从原路径读视频；转写输出写入 `./output/<文件名无后缀>/`。若原文件名含路径非法字符，会经 `sanitize_job_name` 处理后再作为目录名。

## 项目结构

```
videoAIconclusion/
├── README.md
├── requirements.txt
├── env.example                 # 复制为 .env 使用
├── video_pipeline/
│   ├── __init__.py
│   ├── __main__.py             # CLI 入口
│   ├── download.py             # yt-dlp 下载（B 站等）
│   ├── extract.py              # FFmpeg 抽 WAV
│   ├── transcribe.py           # faster-whisper + 简体规范化
│   └── summarize.py            # OpenAI 兼容 Chat Completions
└── output/                     # 默认工作区根（运行后生成，已 .gitignore）
```

默认工作目录为项目下的 `output/<视频名>/`，体积较大，已加入 `.gitignore`；如需纳入版本库可自行调整。

也可在自有脚本中 `import video_pipeline.extract` / `transcribe` / `summarize` 按需组合。

## 中文与编码说明

- 转写默认 `--language zh`；若检测或指定为中文，会对片段文本做 **zh-cn** 字形转换，便于统一为大陆常用简体写法。  
- 非中文内容（例如 `--language en`）不会做简繁转换。  
- 凡文本写入均使用 **UTF-8**，便于后续编辑器、检索或再接入其他工具。

## 许可证

未在仓库内单独声明许可证；使用上游项目（FFmpeg、faster-whisper、各 API 服务商）时请遵守其各自条款。
