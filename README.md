# AISubsTools
AISubsTools是一个利用 OpenAI 的 Whisper 模型和LLM实现AI音频转写与翻译的简易网页GUI。本工程的基础代码由Gemini-2.5-Pro生成。
## ✨ 主要功能
- **视频音频自动转写**: 利用 OpenAI 的 Whisper 模型，高精度地将 MP4 视频或 MP3 音频文件转写为 SRT 格式的字幕。

    - 支持 MP4 自动转换为 MP3。
    - 支持多种 Whisper 模型尺寸 (tiny, base, small, medium, large) 以平衡速度与精度。
    - 支持指定源语言（中/英/日），以提高特定语言的识别准确率。

- **字幕智能翻译**: 对接本地部署的 Ollama 服务，调用任意大语言模型对 SRT 字幕进行翻译。

    - 自动检测并列出 Ollama 中可用的所有模型。
    - 生成中英/中日双语对照的SRT字幕文件，保留原文以供校对。
## 🚀 安装与部署
### 系统依赖

在运行本项目前，请确保您的系统中已安装以下软件：

- Python 3.8+

- FFmpeg: 必须安装并配置好系统环境变量。

- Ollama: 请根据 Ollama 官网 的指引进行安装。安装后，请至少拉取一个用于翻译的模型，例如：
```bash
ollama pull zongwei/gemma3-translator:4b
```
### 项目设置
#### 克隆本项目仓库
```bash
git clone [<your-repository-url>](https://github.com/JiDongHuangPlus/ai_subs_tools.git)
cd ai_subs_tools
```
#### 安装 Python 依赖
```bash
pip install -r requirements.txt
```
注意：openai-whisper 库在首次运行时会自动下载所选尺寸的模型文件，请确保网络通畅并耐心等待。

## ▶️ 运行应用
在项目根目录下，执行以下命令：
```bash
python app.py
```
启动成功后，您会看到类似如下输出：
```bash
 * Running on http://0.0.0.0:5000
```
现在，您可以在浏览器中通过 http://127.0.0.1:5000 或 http://<您的局域网IP>:5000 来访问本应用。

## 📖 使用指南
### Whisper 生成字幕:

- 在左侧卡片中，上传您的 MP4 或 MP3 文件。

- 选择视频的“源语言”和期望的“Whisper 模型”。

- 点击“开始生成”。任务完成后，新生成的 .srt 文件会出现在下方的“Outputs 文件夹”管理区域。

### Ollama 翻译字幕:

- 在右侧卡片中，上传您需要翻译的 .srt 文件。

- 输入您本地 Ollama 服务的 IP 地址（若在本机运行，则为 127.0.0.1），然后点击“获取模型”。

- 从下拉菜单中选择一个翻译模型。

- 点击“开始翻译”。任务将以进度条形式显示，完成后，双语 .srt 文件同样会出现在“Outputs 文件夹”中。

### 文件管理:

- 在下方的文件管理区，您可以通过标签页切换查看 Outputs 和 Uploads 文件夹的内容。

- 点击“刷新”按钮可随时更新文件列表。

- 每个文件后都提供了“下载”和“删除”按钮。

- 点击右上角的“清空”按钮可删除对应文件夹内的所有文件（操作前会有确认提示）。