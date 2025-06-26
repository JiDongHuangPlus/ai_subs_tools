# translation_utils.py

import srt
import subprocess
import json
import re
import os

BATCH_TRANSLATION_PROMPT = """You are a professional subtitle translator. Your task is to translate a batch of numbered Japanese subtitle lines into Simplified Chinese, ensuring contextual coherence.

Follow these rules strictly:
1. Translate all the lines provided.
2. Maintain the original numbering for each corresponding translation.
3. Output only the numbered list of translations, without any additional comments, introductions, or explanations.

Here are the lines to translate:

{text}
"""

def get_ollama_models(host_ip, port=11434):
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
        
        translated_lines_map = {int(num): text.strip() for num, text in re.findall(r'^\s*(\d+)\s*[.\s]\s*(.*)', raw_translation, re.MULTILINE)}
        
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

def process_srt_translation(input_path, output_path, ollama_host, ollama_port, ollama_model, batch_size=10, progress_callback=None):
    api_endpoint = f"http://{ollama_host}:{ollama_port}/api/chat"
    
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            subtitles = list(srt.parse(f.read()))
        total_subs = len(subtitles)

        new_subtitles = []
        for i in range(0, total_subs, batch_size):
            if progress_callback:
                progress = int((i / total_subs) * 100)
                progress_callback(progress)

            batch_start = i
            batch_end = min(i + batch_size, total_subs)
            current_batch_subs = subtitles[batch_start:batch_end]
            
            batch_texts_to_translate = [f"{idx + 1}. {sub.content.strip()}" for idx, sub in enumerate(current_batch_subs)]
            prompt_text = "\n".join(batch_texts_to_translate)
            
            translated_lines = translate_batch_with_curl(prompt_text, api_endpoint, ollama_model, len(current_batch_subs))

            for j, sub in enumerate(current_batch_subs):
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
        return False