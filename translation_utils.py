# translation_utils.py

import srt
import subprocess
import json
import re
import os
import concurrent.futures
from concurrent.futures import as_completed

# 提示保持不变
BATCH_TRANSLATION_PROMPT = """You are a professional subtitle translator. Your task is to translate a batch of numbered subtitle lines into Simplified Chinese, ensuring contextual coherence.

Follow these rules strictly:
1. Translate all the lines provided.
2. Maintain the original numbering for each corresponding translation.
3. Output only the numbered list of translations, without any additional comments, introductions, or explanations.

Here are the lines to translate:

{text}
"""

def get_ollama_models(host_ip, port=11434):
    """获取Ollama可用模型列表，此函数保持不变。"""
    api_endpoint = f"http://{host_ip}:{port}/api/tags"
    curl_command = ['curl', '-s', api_endpoint]
    
    try:
        result = subprocess.run(
            curl_command, capture_output=True, text=True, check=True, encoding='utf-8', timeout=30
        )
        response_data = json.loads(result.stdout)
        model_names = [model.get('name') for model in response_data.get('models', [])]
        return model_names
    except subprocess.TimeoutExpired:
        print(f"  [!] Error: CURL command to {api_endpoint} timed out.")
        return {"error": "Connection timed out. Check if Ollama is running and the IP is correct."}
    except Exception as e:
        print(f"  [!] An error occurred while fetching Ollama models: {e}")
        return {"error": str(e)}


def translate_batch_with_curl(text_batch, api_endpoint, model, expected_line_count):
    """
    使用CURL调用Ollama API进行批量翻译。
    此函数也保持不变，它将被并发调用。
    """
    prompt = BATCH_TRANSLATION_PROMPT.format(text=text_batch)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }
    json_payload = json.dumps(payload)

    curl_command = [
        'curl', '-s', api_endpoint, '-X', 'POST',
        '-H', 'Content-Type: application/json', '--data', json_payload
    ]

    try:
        result = subprocess.run(
            curl_command, capture_output=True, text=True, check=True, encoding='utf-8', timeout=300
        )
        response_data = json.loads(result.stdout)
        raw_translation = response_data.get('message', {}).get('content', '')
        
        # 解析返回的编号列表
        translated_lines_map = {int(num): text.strip() for num, text in re.findall(r'^\s*(\d+)\s*[.\s]\s*(.*)', raw_translation, re.MULTILINE)}
        
        # 按原始顺序构建翻译列表，处理缺失的行
        final_translations = [translated_lines_map.get(i, f"[翻译缺失 Line {i}]") for i in range(1, expected_line_count + 1)]

        if len(final_translations) != expected_line_count:
            print(f"  [!] Warning: Expected {expected_line_count} translations, but parsed {len(final_translations)}.")
        
        return final_translations

    except subprocess.TimeoutExpired:
        print(f"  [!] Error: CURL command timed out.")
        return ["[CURL超时]"] * expected_line_count
    except Exception as e:
        print(f"  [!] An error occurred during batch translation: {e}")
        return ["[批量翻译失败]"] * expected_line_count


def process_srt_translation(input_path, output_path, ollama_host, ollama_port, ollama_model, batch_size=10, progress_callback=None, max_workers=5):
    """
    【核心修改】使用ThreadPoolExecutor并发处理SRT文件的翻译。
    """
    api_endpoint = f"http://{ollama_host}:{ollama_port}/api/chat"
    
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            subtitles = list(srt.parse(f.read()))
        
        total_subs = len(subtitles)
        # 用于存储所有批次的结果，键为批次起始索引，值为翻译结果
        all_results = {}
        
        # 使用线程池执行并发翻译
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 创建一个字典来存储 future -> batch_info 的映射
            future_to_batch = {}
            
            # 提交所有批次任务
            for i in range(0, total_subs, batch_size):
                batch_start = i
                batch_end = min(i + batch_size, total_subs)
                current_batch_subs = subtitles[batch_start:batch_end]
                
                batch_texts_to_translate = [f"{idx + 1}. {sub.content.strip()}" for idx, sub in enumerate(current_batch_subs)]
                prompt_text = "\n".join(batch_texts_to_translate)
                
                # 提交任务到线程池
                future = executor.submit(translate_batch_with_curl, prompt_text, api_endpoint, ollama_model, len(current_batch_subs))
                future_to_batch[future] = {'start_index': batch_start, 'subs': current_batch_subs}

            completed_count = 0
            # 当任务完成时，处理结果并更新进度条
            for future in as_completed(future_to_batch):
                batch_info = future_to_batch[future]
                try:
                    translated_lines = future.result()
                    all_results[batch_info['start_index']] = (batch_info['subs'], translated_lines)
                except Exception as exc:
                    print(f"  [!] Batch from index {batch_info['start_index']} generated an exception: {exc}")
                    # 即使失败，也创建一个占位符结果，以防程序崩溃
                    placeholder_error = ["[批次处理异常]"] * len(batch_info['subs'])
                    all_results[batch_info['start_index']] = (batch_info['subs'], placeholder_error)
                
                # 更新进度
                completed_count += len(batch_info['subs'])
                if progress_callback:
                    progress = int((completed_count / total_subs) * 100)
                    progress_callback(progress)

        # 确保所有批次都处理完毕后，按顺序组装新的字幕文件
        new_subtitles = []
        # 按批次的起始索引排序，以确保字幕顺序正确
        sorted_indices = sorted(all_results.keys())
        
        for index in sorted_indices:
            original_subs, translated_lines = all_results[index]
            for j, sub in enumerate(original_subs):
                translated_text = translated_lines[j] if j < len(translated_lines) else "[翻译结果缺失]"
                new_content = f"{sub.content.strip()}\n{translated_text}"
                new_subtitles.append(srt.Subtitle(index=sub.index, start=sub.start, end=sub.end, content=new_content))

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(srt.compose(new_subtitles))
            
        if progress_callback:
            progress_callback(100)
            
        return True

    except Exception as e:
        print(f"[!] An unexpected error occurred during SRT processing: {e}")
        # 如果并发过程中出错，确保回调也能反映失败
        if progress_callback:
            progress_callback(-1) # 使用-1等特殊值表示错误
        return False