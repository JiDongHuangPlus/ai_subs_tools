# tasks.py

import os
import subprocess
import whisper
import translation_utils

# 任务状态存储 (只为需要进度的任务服务)
tasks = {}

def run_transcription(file_path, language, model_size, base_name, output_dir):
    """
    在后台直接运行Whisper转录，此版本不汇报进度，直接返回结果或错误。
    """
    try:
        # 1. 如果是 MP4，转为 MP3
        if file_path.lower().endswith('.mp4'):
            # 注意：这里的输出路径需要明确指定
            audio_path = os.path.join(output_dir, f"{base_name}.mp3")
            subprocess.run(
                ['ffmpeg', '-i', file_path, '-y', '-vn', '-acodec', 'libmp3lame', '-q:a', '2', audio_path],
                check=True, capture_output=True, text=True
            )
        else:
            audio_path = file_path

        # 2. 使用 Whisper 生成 SRT
        model = whisper.load_model(model_size)
        result = model.transcribe(audio_path, language=language, fp16=False)

        # 3. 保存 SRT 文件
        srt_filename = f"{base_name}.srt"
        srt_path = os.path.join(output_dir, srt_filename)
        
        with open(srt_path, "w", encoding="utf-8") as srt_file:
            for i, segment in enumerate(result['segments']):
                start_time = segment['start']
                end_time = segment['end']
                text = segment['text'].strip()
                start_srt_time = f"{int(start_time//3600):02}:{int((start_time%3600)//60):02}:{int(start_time%60):02},{int((start_time*1000)%1000):03}"
                end_srt_time = f"{int(end_time//3600):02}:{int((end_time%3600)//60):02}:{int(end_time%60):02},{int((end_time*1000)%1000):03}"
                srt_file.write(f"{i + 1}\n{start_srt_time} --> {end_srt_time}\n{text}\n\n")

        # 成功，返回结果字典
        return {
            "success": True,
            "filename": srt_filename,
            "download_url": f"/outputs/{srt_filename}"
        }

    except subprocess.CalledProcessError as e:
        # FFMPEG 错误
        error_message = f"FFMPEG Error: {e.stderr}"
        print(error_message)
        return {"error": error_message}
    except Exception as e:
        # 其他错误
        error_message = f"An error occurred: {e}"
        print(error_message)
        return {"error": error_message}


def run_translation(task_id, input_path, output_path, ollama_host, ollama_model):
    """在后台线程中运行翻译，并回调进度"""
    global tasks
    tasks[task_id]['status'] = 'processing'
    
    def progress_callback(progress):
        tasks[task_id]['progress'] = progress

    try:
        success = translation_utils.process_srt_translation(
            input_path=input_path,
            output_path=output_path,
            ollama_host=ollama_host,
            ollama_port=11434,
            ollama_model=ollama_model,
            progress_callback=progress_callback
        )
        if success:
            tasks[task_id].update({
                'status': 'completed',
                'progress': 100,
                'result': {
                    'filename': os.path.basename(output_path),
                    'download_url': f"/outputs/{os.path.basename(output_path)}"
                }
            })
        else:
            raise Exception("Translation process returned failure.")
            
    except Exception as e:
        print(f"Error during translation: {e}")
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)