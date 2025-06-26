# app.py

import os
import uuid
import threading
import shutil
from flask import Flask, request, render_template, jsonify, send_from_directory
from werkzeug.utils import secure_filename

# 确保 tasks.py 文件与 app.py 在同一目录下
from tasks import tasks, run_transcription, run_translation
import translation_utils

# --- 配置 ---
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS_MEDIA = {'mp4', 'mp3'}
ALLOWED_EXTENSIONS_SRT = {'srt'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024

# --- 启动时确保目录存在 ---
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# --- 辅助函数 ---
def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


# --- Flask 路由 ---

@app.route('/')
def index():
    return render_template('index.html')

# --- 核心功能路由 (不变) ---
@app.route('/get-ollama-models', methods=['POST'])
def get_models():
    data = request.get_json()
    host_ip = data.get('host_ip')
    if not host_ip: return jsonify({"error": "Host IP is required."}), 400
    models_or_error = translation_utils.get_ollama_models(host_ip)
    if isinstance(models_or_error, dict) and 'error' in models_or_error:
        return jsonify(models_or_error), 500
    return jsonify({"models": models_or_error})

@app.route('/transcribe', methods=['POST'])
def transcribe_media():
    if 'file' not in request.files: return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename, ALLOWED_EXTENSIONS_MEDIA):
        return jsonify({"error": "Invalid file type"}), 400
    filename = secure_filename(file.filename)
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(upload_path)
    result = run_transcription(file_path=upload_path, language=request.form.get('language'),
                               model_size=request.form.get('model', 'base'),
                               base_name=os.path.splitext(filename)[0],
                               output_dir=app.config['OUTPUT_FOLDER'])
    if 'error' in result: return jsonify(result), 500
    return jsonify(result)

@app.route('/translate', methods=['POST'])
def translate_srt():
    if 'file' not in request.files: return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename, ALLOWED_EXTENSIONS_SRT):
        return jsonify({"error": "Invalid file type"}), 400
    filename = secure_filename(file.filename)
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(upload_path)
    ollama_host = request.form.get('ollama_host')
    ollama_model = request.form.get('ollama_model')
    if not all([ollama_host, ollama_model]):
        return jsonify({"error": "Ollama Host and Model are required."}), 400
    output_filename = f"{os.path.splitext(filename)[0]}.bilingual.srt"
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
    task_id = str(uuid.uuid4())
    tasks[task_id] = {'status': 'pending', 'progress': 0}
    thread = threading.Thread(target=run_translation, args=(task_id, upload_path, output_path, ollama_host, ollama_model))
    thread.start()
    return jsonify({'task_id': task_id})

@app.route('/status/<task_id>')
def task_status(task_id):
    task = tasks.get(task_id)
    if not task: return jsonify({'status': 'not_found'}), 404
    return jsonify(task)

# --- 文件管理路由 (已修正所有名称) ---

def manage_folder(action, folder_type, filename=None):
    """通用文件夹管理函数，减少代码重复"""
    folder_path = app.config['UPLOAD_FOLDER'] if folder_type == 'uploads' else app.config['OUTPUT_FOLDER']

    try:
        if action == 'list':
            files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
            files.sort(key=lambda x: os.path.getmtime(os.path.join(folder_path, x)), reverse=True)
            return jsonify({"files": files})

        if action == 'clear':
            for f in os.listdir(folder_path):
                file_path = os.path.join(folder_path, f)
                if os.path.isfile(file_path) or os.path.islink(file_path): os.unlink(file_path)
                elif os.path.isdir(file_path): shutil.rmtree(file_path)
            return jsonify({"status": "success", "message": f"文件夹 '{folder_path}' 已清空。"})

        if action == 'delete':
            if '..' in filename or filename.startswith('/'):
                return jsonify({"status": "error", "message": "无效的文件名。"}), 400
            file_path = os.path.join(folder_path, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                return jsonify({"status": "success", "message": f"文件 '{filename}' 已删除。"})
            else:
                return jsonify({"status": "error", "message": "文件未找到。"}), 404
                
        if action == 'download':
             return send_from_directory(folder_path, filename, as_attachment=True)

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Outputs 文件夹管理
@app.route('/outputs-download/<path:filename>')
def download_output_file(filename): return manage_folder('download', 'outputs', filename)

@app.route('/outputs-files', methods=['GET'])
def list_output_files(): return manage_folder('list', 'outputs')

@app.route('/clear-outputs', methods=['POST'])
def clear_outputs(): return manage_folder('clear', 'outputs')

@app.route('/delete-outputs-file/<path:filename>', methods=['POST'])
def delete_output_file(filename): return manage_folder('delete', 'outputs', filename)

# Uploads 文件夹管理
@app.route('/uploads-download/<path:filename>')
def download_upload_file(filename): return manage_folder('download', 'uploads', filename)

@app.route('/uploads-files', methods=['GET'])
def list_upload_files(): return manage_folder('list', 'uploads')

@app.route('/clear-uploads', methods=['POST'])
def clear_uploads(): return manage_folder('clear', 'uploads')

@app.route('/delete-uploads-file/<path:filename>', methods=['POST'])
def delete_upload_file(filename): return manage_folder('delete', 'uploads', filename)

# --- 主程序入口 ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
