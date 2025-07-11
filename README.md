# SubtitlesTools

一个基于 PyQt6 的字幕处理工具，支持字幕翻译和格式转换功能。

## 功能特性

- 字幕文件翻译（基于 OpenAI API）
- 音频转文字并翻译
- SRT 格式转 ASS 格式
- 可视化界面操作
- 支持自定义ass样式并一键srt转ass
- 支持自己制作内封字幕

## 安装指南

### 1. 下载项目

将项目下载到本地：

```bash
git clone [项目地址]
cd SubtitlesTools
```

### 2. 安装依赖

执行以下命令安装 Python 依赖：

```bash
pip install -r requirements.txt
```

### 3. 下载 FFmpeg

- 访问 [FFmpeg 官网](https://ffmpeg.org/download.html)
- 下载适合你操作系统的 FFmpeg 版本
- 解压下载的文件，并将文件夹重命名为 `ffmpeg`
- 将 `ffmpeg` 文件夹放入项目根目录

### 4. 项目结构

确保你的项目目录结构如下：

```
SubtitlesTools/
├── config/
│   ├── ass_config.json
│   └── setting.json
├── ffmpeg/
│   ├── LICENSE
│   ├── bin/
│   │   ├── ffmpeg.exe
│   │   ├── ffplay.exe
│   │   └── ffprobe.exe
│   └── presets/
│       ├── libvpx-1080p.ffpreset
│       ├── libvpx-1080p50_60.ffpreset
│       ├── libvpx-360p.ffpreset
│       ├── libvpx-720p.ffpreset
│       └── libvpx-720p50_60.ffpreset
├── main.py
├── output/
├── requirements.txt
├── static/
│   └── loading.gif
├── test/
└── utils/
   ├── audio_translator.py
   ├── openai_api.py
   ├── subtitle_translator.py
   └── video_info.py
```

## 配置设置

### OpenAI API 配置

打开 `config/setting.json` 文件，填写你的 OpenAI API 密钥：

```json
{
 "api_key": "你的OpenAI API密钥",
 "text_models": ["gpt-3.5-turbo", "gpt-4"],
 "audio_models": ["whisper-1"],
 "default_output_path": "./output"
}
```

**配置说明：**
- `api_key`: 你的 OpenAI API 密钥
- `text_models`: 文本翻译模型列表
- `audio_models`: 语音翻译模型列表  
- `default_output_path`: 默认输出文件夹路径

### 字幕样式配置

`config/ass_config.json` 文件用于配置 SRT 格式转 ASS 字幕的样式，你可以根据需要自定义配置。

## 使用方法

配置完成后，运行以下命令启动应用：

```bash
python main.py
```

## 系统要求

- Python 3.7+
- PyQt6
- OpenCV
- OpenAI API 密钥
- FFmpeg

## 注意事项

- 由于时间有限，目前只集成了 OpenAI 的 API
- 后续有时间会考虑接入其他模型以及增加更多功能
- 使用前请确保你有有效的 OpenAI API 密钥并且账户有足够的余额
