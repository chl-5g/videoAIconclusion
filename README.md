# videoAIconclusion

本地视频（或已有文件）的「抽音频 → 语音转写 →（可选）大模型总结」流水线，组件可拆开替换：FFmpeg、faster-whisper、任意 **OpenAI 兼容** Chat Completions 接口。

## 流程概览

1. **FFmpeg**：从视频导出 16 kHz 单声道 PCM WAV，供 Whisper 使用。  
2. **Faster-Whisper**：转写为带时间戳的片段；默认按中文解码，并对中文结果做 **简体字形** 规范化（`zhconv`）。  
3. **HTTP API 总结**：将全文逐字稿 POST 到 `/v1/chat/completions`；未配置 API 密钥时只输出转写。

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

需要总结步骤时，复制环境变量模板并填写：

```bash
cp env.example .env
# 编辑 .env；程序启动时会通过 python-dotenv 自动加载（若已安装）
```

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | 调用总结接口的密钥；仅转写时可不设。 |
| `OPENAI_BASE_URL` | 可选，默认 `https://api.openai.com/v1`。DeepSeek、自建网关、Ollama（`http://127.0.0.1:11434/v1`）等填对应前缀。 |
| `LLM_MODEL` | 可选，默认 `gpt-4o-mini`；例如 DeepSeek 可用 `deepseek-chat`。 |

## 命令行用法

在项目根目录执行（保证当前工作目录包含 `video_pipeline` 包）：

```bash
python -m video_pipeline /path/to/video.mp4 -o output
```

常用参数：

| 参数 | 含义 |
|------|------|
| `-o`, `--out` | 输出目录，默认 `output`。 |
| `--whisper-model` | `tiny` / `base` / `small` / `medium` / `large-v3` 等；机器较慢时优先减小模型。 |
| `--device` | `cpu`（默认）或 `cuda`。 |
| `--compute-type` | CPU 上常用 `int8`；CUDA 可试 `float16`。 |
| `--language` | 默认 `zh`（中文转写）；`auto` 为自动检测语言；也可显式指定 `en` 等。 |
| `--skip-summary` | 只跑转写，不请求大模型。 |
| `--max-chars` | 送入模型的逐字稿最大字符数，默认 `120000`，超出会截断并标注。 |

示例：

```bash
# 仅转写，适合离线或不想配 API
python -m video_pipeline ./demo.mp4 -o ./output --skip-summary

# 弱 CPU：更小模型
python -m video_pipeline ./demo.mp4 --whisper-model base

# 英文视频
python -m video_pipeline ./talk.mp4 --language en
```

## 输出文件

假定视频文件名为 `demo.mp4`，输出目录为 `output/`：

| 文件 | 说明 |
|------|------|
| `demo_16k.wav` | 中间音频，可删可留。 |
| `demo_transcript.json` | 片段列表：`start` / `end` / `text`，顶层含检测语言字段；UTF-8，`ensure_ascii=False`。 |
| `demo_transcript.txt` | 纯文本逐字稿，UTF-8。 |
| `demo_transcript_timestamped.txt` | 带 `[起始s - 结束s]` 前缀的逐行文本，UTF-8。 |
| `demo_summary.md` | 在已设置 `OPENAI_API_KEY` 且未 `--skip-summary` 时生成，中文要点式总结。 |

## 项目结构

```
videoAIconclusion/
├── README.md
├── requirements.txt
├── env.example                 # 复制为 .env 使用
├── video_pipeline/
│   ├── __init__.py
│   ├── __main__.py             # CLI 入口
│   ├── extract.py              # FFmpeg 抽 WAV
│   ├── transcribe.py           # faster-whisper + 简体规范化
│   └── summarize.py            # OpenAI 兼容 Chat Completions
└── output/                     # 默认输出目录（运行后生成，已 .gitignore）
```

也可在自有脚本中 `import video_pipeline.extract` / `transcribe` / `summarize` 按需组合。

## 中文与编码说明

- 转写默认 `--language zh`；若检测或指定为中文，会对片段文本做 **zh-cn** 字形转换，便于统一为大陆常用简体写法。  
- 非中文内容（例如 `--language en`）不会做简繁转换。  
- 凡文本写入均使用 **UTF-8**，便于后续编辑器、检索或再接入其他工具。

## 许可证

未在仓库内单独声明许可证；使用上游项目（FFmpeg、faster-whisper、各 API 服务商）时请遵守其各自条款。
