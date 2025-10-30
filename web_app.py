from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS  # 导入CORS支持
import os
import subprocess
import json
import time
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
import threading
import queue
from functools import wraps
import traceback
import logging
import config_manager  # 导入配置管理模块
from markdown_renderer import renderer  # 导入Markdown渲染器

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def log_info(message):
    """记录信息日志"""
    logger.info(message)

def log_error(message):
    """记录错误日志"""
    logger.error(message)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB max file size，提高限制以支持更大的PPT文件
CORS(app)  # 启用CORS支持，允许跨域请求

# 确保目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
os.makedirs('.wucai', exist_ok=True)

# 允许上传的文件扩展名
ALLOWED_EXTENSIONS = {'pdf', 'md', 'markdown', 'ppt', 'pptx', 'py'}

# 任务队列和状态管理
task_queue = queue.Queue()
task_status = {}  # {task_id: {'status': 'pending|processing|completed|failed', 'result': ..., 'progress': ...}}

# 任务状态文件路径
TASK_STATUS_FILE = os.path.join('.wucai', 'task_status.json')

# 从文件加载任务状态
def load_task_status():
    """
    从JSON文件加载任务状态，实现任务状态持久化
    """
    global task_status
    if os.path.exists(TASK_STATUS_FILE):
        try:
            with open(TASK_STATUS_FILE, 'r', encoding='utf-8') as f:
                task_status = json.load(f)
            log_info("已从文件加载任务状态")
        except (json.JSONDecodeError, FileNotFoundError, IOError) as e:
            log_error(f"加载任务状态文件时出错: {str(e)}")
            task_status = {}

# 保存任务状态到文件
def save_task_status():
    """
    将当前任务状态保存到JSON文件
    """
    try:
        with open(TASK_STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(task_status, f, ensure_ascii=False, indent=2)
    except (IOError, TypeError) as e:
        log_error(f"保存任务状态文件时出错: {str(e)}")

# 初始化时加载任务状态
load_task_status()

import traceback

def exception_handler(f):
    """
    全局异常处理装饰器，捕获函数中的异常并记录到错误日志
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            # 创建一个临时任务ID用于记录异常
            temp_task_id = str(uuid.uuid4())
            log_error(f"未处理异常 {temp_task_id}: {str(e)}")
            # 同时记录到详细错误日志文件
            log_error_detail(temp_task_id, "unknown", str(e), "unhandled_exception")
            # 重新抛出异常或返回错误响应，取决于函数的预期行为
            return jsonify({'error': f'系统错误: {str(e)}'}), 500
    return decorated_function

def log_error_detail(task_id, file_path, error_message, error_type="processing_error", stack_trace=None):
    """
    记录错误日志到专门的错误日志文件
    
    Args:
        task_id: 任务ID
        file_path: 输入文件路径
        error_message: 错误信息
        error_type: 错误类型
        stack_trace: 错误堆栈跟踪（可选）
    """
    error_log = {
        "error_id": str(uuid.uuid4()),
        "task_id": task_id,
        "input_file": os.path.basename(file_path) if file_path else "unknown",
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "error_type": error_type,
        "error_message": error_message,
        "stack_trace": stack_trace or traceback.format_exc(),  # 记录完整的堆栈跟踪
        "processing_time": time.time()
    }
    
    # 错误日志文件路径
    error_log_file = os.path.join('.wucai', 'error_logs.json')
    
    # 读取现有错误日志
    error_logs = []
    if os.path.exists(error_log_file):
        try:
            with open(error_log_file, 'r', encoding='utf-8') as f:
                error_logs = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            error_logs = []
    
    # 添加新的错误日志
    error_logs.append(error_log)
    
    # 限制错误日志数量，保留最新的1000条
    if len(error_logs) > 1000:
        error_logs = error_logs[-1000:]
    
    # 写入错误日志文件
    with open(error_log_file, 'w', encoding='utf-8') as f:
        json.dump(error_logs, f, ensure_ascii=False, indent=2)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_task(task_id, file_paths, api_key, prompt, output_path):
    """处理单个任务的函数，支持多个文件"""
    global task_status
    
    try:
        # 加载配置
        config = config_manager.load_config()
        
        # 更新任务状态为处理中
        task_status[task_id]['status'] = 'processing'
        task_status[task_id]['progress'] = 5  # 开始处理
        save_task_status()  # 保存状态到文件
        
        # 不设置环境变量，使用config_manager中的配置
        env = os.environ.copy()
        # 移除可能存在的旧环境变量
        for key in ['DASHSCOPE_API_KEY', 'TEXT_MODEL', 'IMAGE_MODEL']:
            if key in env:
                del env[key]
        
        # 构建命令 - 针对多文件处理
        cmd = [
            'python', 'pdf_to_knowledge_md.py'
        ]
        
        # 只在prompt不为空时添加--prompt参数
        if prompt:
            cmd.extend(['--prompt', prompt])
            
        cmd.extend(['--output', output_path])
        
        # 使用传入的api_key或配置中的api_key
        api_key_to_use = api_key or config.get('api_key', '')
        if api_key_to_use:
            cmd.extend(['--api-key', api_key_to_use])
        
        # 添加所有文件路径到命令（确保文件路径在所有选项参数之后）
        for file_path in file_paths:
            cmd.append(file_path)
        
        # 更新进度到20%
        task_status[task_id]['progress'] = 20
        save_task_status()  # 保存状态到文件
        
        # 执行处理 - 使用二进制模式避免编码问题
        result = subprocess.run(
            cmd,
            capture_output=True,
            env=env,
            timeout=600  # 增加超时时间以支持多文件处理
        )
        
        # 更新进度到80%
        task_status[task_id]['progress'] = 80
        save_task_status()  # 保存状态到文件
        
        # 手动解码输出，使用UTF-8编码并处理可能的解码错误
        try:
            stdout_str = result.stdout.decode('utf-8')
        except UnicodeDecodeError:
            # 如果UTF-8解码失败，使用系统默认编码并替换错误字符
            stdout_str = result.stdout.decode('utf-8', errors='replace')

        try:
            stderr_str = result.stderr.decode('utf-8')
        except UnicodeDecodeError:
            # 如果UTF-8解码失败，使用系统默认编码并替换错误字符
            stderr_str = result.stderr.decode('utf-8', errors='replace')

        if result.returncode == 0:
            # 处理成功
            end_time = time.time()
            processing_duration = end_time - task_status[task_id]['start_time']  # 计算总处理时间（秒）
            
            # 获取输出文件的大小（字数）
            output_length = 0
            if os.path.exists(output_path):
                with open(output_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    output_length = len(content)
                    
            # 从子进程输出中提取token用量
            token_usage = 0
            image_token_usage = 0
            import re
            
            # 检查标准输出中的文本处理token用量
            token_match = re.search(r'TOKEN_USAGE:(\d+)', stdout_str)
            if token_match:
                token_usage = int(token_match.group(1))
                log_info(f"任务 {task_id} 从子进程输出中提取到文本处理token用量: {token_usage}")
            else:
                # 尝试从错误输出中查找（以防万一输出到stderr）
                token_match = re.search(r'TOKEN_USAGE:(\d+)', stderr_str)
                if token_match:
                    token_usage = int(token_match.group(1))
                    log_info(f"任务 {task_id} 从错误输出中提取到文本处理token用量: {token_usage}")
                else:
                    log_info(f"任务 {task_id} 未找到文本处理token用量信息")
            
            # 检查标准输出中的图像识别token用量
            image_token_matches = re.findall(r'IMAGE_TOKEN_USAGE:(\d+)', stdout_str)
            if image_token_matches:
                for match in image_token_matches:
                    image_token_usage += int(match)
                log_info(f"任务 {task_id} 从子进程输出中提取到图像识别token用量: {image_token_usage}")
            else:
                # 尝试从错误输出中查找
                image_token_matches = re.findall(r'IMAGE_TOKEN_USAGE:(\d+)', stderr_str)
                if image_token_matches:
                    for match in image_token_matches:
                        image_token_usage += int(match)
                    log_info(f"任务 {task_id} 从错误输出中提取到图像识别token用量: {image_token_usage}")
            
            # 计算总token用量
            total_token_usage = token_usage + image_token_usage
            log_info(f"任务 {task_id} 总token用量: {total_token_usage} (文本处理: {token_usage} + 图像识别: {image_token_usage})")

            task_status[task_id]['status'] = 'completed'
            task_status[task_id]['progress'] = 100
            # 将处理时间和输出字数作为顶级字段，方便前端访问
            task_status[task_id]['processing_time'] = processing_duration  # 以秒为单位的处理时间
            task_status[task_id]['output_length'] = output_length  # 输出字数
            task_status[task_id]['token_usage'] = total_token_usage  # 设置实际的总token用量
            task_status[task_id]['image_token_usage'] = image_token_usage  # 记录图像识别token用量
            
            task_status[task_id]['result'] = {
                'output_file': os.path.basename(output_path),
                'message': '处理成功',
                'processing_time': processing_duration,  # 以秒为单位的处理时间
                'output_length': output_length,  # 输出字数
                'token_usage': total_token_usage,  # 使用实际计算的总token用量
                'image_token_usage': image_token_usage  # 记录图像识别token用量
            }
            save_task_status()  # 保存状态到文件
            
            # 保存处理记录
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 构建输入文件描述
            input_file_desc = ', '.join(task_status[task_id]['input_filenames'])
            
            record = {
                'task_id': task_id,
                'input_file': input_file_desc,  # 显示多个文件名
                'unique_input_files': [os.path.basename(fp) for fp in file_paths],  # 内部存储的安全文件名列表
                'output_file': os.path.basename(output_path),  # 包含原始文件名的输出文件名
                'prompt': prompt,
                'timestamp': timestamp,
                'processing_time': task_status[task_id]['start_time'],  # 任务开始的Unix时间戳
                'duration_seconds': processing_duration,  # 处理耗时（秒）
                'status': 'completed',
                'output_length': output_length,  # 输出字数
                'token_usage': total_token_usage,  # 使用总token用量
                'image_token_usage': image_token_usage  # 添加图像识别token用量记录
            }
            
            # 保存到JSON记录文件
            records_file = os.path.join('.wucai', 'processing_records.json')
            records = []
            if os.path.exists(records_file):
                try:
                    with open(records_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:  # 检查文件内容是否为空
                            records = json.loads(content)
                        else:
                            records = []  # 空文件则初始化为空列表
                except (json.JSONDecodeError, FileNotFoundError):
                    records = []  # 如果解析失败或文件不存在，初始化为空列表
            
            records.append(record)
            
            with open(records_file, 'w', encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
                
        else:
            # 处理失败 - 现在能更好地捕获子进程错误
            task_status[task_id]['status'] = 'failed'
            task_status[task_id]['error'] = stderr_str
            task_status[task_id]['progress'] = 100
            task_status[task_id]['result'] = {
                'message': f'处理失败: {stderr_str}'
            }
            save_task_status()  # 保存状态到文件
            
            # 记录错误日志 - 现在会记录到全局错误日志
            log_error(f"任务 {task_id} 错误: {stderr_str}")
            # 同时记录到详细错误日志文件
            log_error_detail(task_id, ', '.join(file_paths), f"处理失败: {stderr_str}", "processing_error")

        task_status[task_id]['end_time'] = time.time()
        save_task_status()  # 保存状态到文件
            
    except subprocess.TimeoutExpired:
        # 处理超时
        task_status[task_id]['status'] = 'failed'
        task_status[task_id]['error'] = "处理超时 (超过10分钟)"
        task_status[task_id]['progress'] = 100
        task_status[task_id]['result'] = {
            'message': '处理超时: 任务执行时间超过10分钟'
        }
        save_task_status()  # 保存状态到文件
        
        # 记录错误日志
        log_error(f"任务 {task_id} 超时错误: 处理超时 (超过10分钟)")
        # 同时记录到详细错误日志文件
        log_error_detail(task_id, ', '.join(file_paths), "处理超时 (超过10分钟)", "timeout_error")
        
        task_status[task_id]['end_time'] = time.time()
        save_task_status()  # 保存状态到文件
        
    except Exception as e:
        # 处理异常
        task_status[task_id]['status'] = 'failed'
        task_status[task_id]['error'] = str(e)
        task_status[task_id]['progress'] = 100
        task_status[task_id]['result'] = {
            'message': f'处理过程中发生错误: {str(e)}'
        }
        save_task_status()  # 保存状态到文件
        
        # 记录错误日志
        log_error(f"任务 {task_id} 异常: {str(e)}")
        # 同时记录到详细错误日志文件
        log_error_detail(task_id, ', '.join(file_paths), str(e), "processing_exception")
        
        task_status[task_id]['end_time'] = time.time()
        save_task_status()  # 保存状态到文件

def task_worker():
    """任务工作线程"""
    while True:
        try:
            task_data = task_queue.get(timeout=1)
            if task_data is None:
                break
            
            task_id = task_data['task_id']
            file_paths = task_data['file_paths']  # 修改为file_paths以支持多个文件
            api_key = task_data['api_key']  # 修改为api_key以符合命名规范
            prompt = task_data['prompt']
            output_path = task_data['output_path']
            
            # 启动处理线程
            processing_thread = threading.Thread(
                target=process_task,
                args=(task_id, file_paths, api_key, prompt, output_path)
            )
            processing_thread.start()
                
            task_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            print(f"任务工作线程错误: {str(e)}")
            continue

# 启动任务工作线程
worker_thread = threading.Thread(target=task_worker, daemon=True)
worker_thread.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        # 检查是否有文件在请求中
        if 'file' not in request.files:
            return jsonify({'error': '没有文件'}), 400
            
        # 获取所有文件
        all_files = request.files.getlist('file')
        
        # 去除重复文件（保留第一个实例）
        files = []
        seen_filenames = set()
        for file in all_files:
            if file.filename != '':
                # 如果文件名已经存在，跳过这个文件
                if file.filename in seen_filenames:
                    log_info(f"跳过重复文件: {file.filename}")
                    continue
                seen_filenames.add(file.filename)
                files.append(file)
        
        if not files:
            return jsonify({'error': '没有选择文件或所有文件都是重复的'}), 400
        
        # 检查是否有不支持的文件格式
        for file in files:
            if not allowed_file(file.filename):
                return jsonify({'error': f'不支持的文件格式: {file.filename}'}), 400
        
        # 获取提示词参数
        prompt = request.form.get('prompt', '')
        
        # 从配置中心读取API Key
        config = config_manager.load_config()
        api_key = config.get('api_key', '')
        # 兼容app_key字段
        if not api_key and 'app_key' in config:
            api_key = config['app_key']
            
        if not api_key:
            return jsonify({'error': 'API Key未配置，请在配置中心设置'}), 400
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 保存上传的文件
        file_paths = []
        original_filenames = []
        
        for file in files:
            if file.filename != '':  # 只处理非空文件
                original_filename = file.filename  # 保存原始文件名（包含中文）
                original_filenames.append(original_filename)
                
                # 提取文件扩展名
                _, file_ext = os.path.splitext(original_filename)
                # 使用task_id和索引作为基础文件名，正确添加扩展名
                secure_unique_filename = f"{task_id}_{len(file_paths)}{file_ext.lower()}"  # 存储时使用安全文件名，保持扩展名格式
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_unique_filename)
                file.save(file_path)
                file_paths.append(file_path)
        
        # 检查是否成功上传了任何文件
        if not file_paths:
            return jsonify({'error': '没有有效的文件被上传'}), 400
        
        # 构建输出文件路径 - 使用原始文件名（保留中文）来构建输出文件名
        # 如果有多个文件，输出文件名为"multiple_files_时间戳.md"
        if len(original_filenames) == 1:
            input_name_without_ext = os.path.splitext(original_filenames[0])[0]
            output_filename = f"{input_name_without_ext}_processed.md"
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f"multiple_files_{timestamp}.md"
        
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        
        # 记录任务开始时间
        start_time = time.time()
        
        # 从配置中心读取模型信息
        text_model = config.get('text_model', 'qwen-plus')
        image_model = config.get('image_model', 'qwen-vl-plus')
        
        # 初始化任务状态
        task_status[task_id] = {
            'status': 'pending',
            'progress': 0,
            'input_filenames': original_filenames,  # 存储原始完整文件名列表
            'start_time': start_time,
            'end_time': None,
            'result': None,
            'error': None,
            'text_model': text_model,
            'image_model': image_model
        }
        save_task_status()  # 保存状态到文件
        
        # 添加任务到队列
        task_data = {
            'task_id': task_id,
            'file_paths': file_paths,  # 修改为file_paths以支持多个文件
            'api_key': api_key,  # 修改为api_key以符合命名规范
            'prompt': prompt,
            'output_path': output_path
        }
        
        task_queue.put(task_data)
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'任务已提交，正在后台处理 {len(file_paths)} 个文件',
            'original_filenames': original_filenames  # 返回原始文件名供前端使用
        })
    except Exception as e:
        # 记录异常
        temp_task_id = str(uuid.uuid4())
        log_error(f"上传过程中发生错误 {temp_task_id}: {str(e)}")
        return jsonify({'error': f'上传过程中发生错误: {str(e)}'}), 500

@app.route('/task_status/<task_id>')
def get_task_status(task_id):
    """获取特定任务的状态"""
    try:
        if task_id in task_status:
            status_info = task_status[task_id].copy()
            # 保留input_filename用于前端显示，但仍然不暴露其他内部路径信息
            # 保留处理用时、token用量和输出字数等信息
            return jsonify(status_info)
        else:
            return jsonify({'error': '任务不存在'}), 404
    except Exception as e:
        temp_task_id = str(uuid.uuid4())
        log_error(f"获取任务状态时发生错误 {temp_task_id}: {str(e)}")
        return jsonify({'error': f'获取任务状态时发生错误: {str(e)}'}), 500

@app.route('/get_config')
def get_config():
    """
    获取当前配置
    """
    try:
        config = config_manager.load_config()
        # 不返回完整的API Key，只返回部分用于显示
        masked_config = config.copy()
        # 修复：同时检查api_key和app_key字段（处理命名不一致问题）
        api_key = masked_config.get('api_key', '')
        # 如果api_key为空，尝试从app_key获取（兼容不同的字段命名）
        if not api_key and 'app_key' in masked_config:
            api_key = masked_config['app_key']
        
        # 获取其他配置项
        text_model = masked_config.get('text_model', '')
        image_model = masked_config.get('image_model', '')
            
        # 修复：只有当所有配置项（api_key、text_model、image_model）都不为空时，小球才亮起
        all_configs_completed = (
            isinstance(api_key, str) and api_key.strip() and
            isinstance(text_model, str) and text_model.strip() and
            isinstance(image_model, str) and image_model.strip()
        )
        
        if isinstance(api_key, str) and api_key.strip():
            masked_config['api_key'] = f"{api_key[:4]}****{api_key[-4:]}" if len(api_key) > 8 else f"{api_key[:2]}****"
        masked_config['api_key_configured'] = all_configs_completed
        
        # 添加模型列表
        masked_config['supported_models'] = {
            'text_models': config_manager.SUPPORTED_MODELS['text_models'],
            'image_models': config_manager.SUPPORTED_MODELS['image_models']
        }
        
        # 添加推荐场景
        masked_config['recommended_scenarios'] = config_manager.RECOMMENDED_SCENARIOS
        
        return jsonify(masked_config)
    except Exception as e:
        temp_task_id = str(uuid.uuid4())
        log_error(f"获取配置时发生错误 {temp_task_id}: {str(e)}")
        return jsonify({'error': f'获取配置时发生错误: {str(e)}'}), 500

@app.route('/update_config', methods=['POST'])
def update_config():
    """
    更新配置
    """
    try:
        data = request.json
        api_key = data.get('api_key', '')
        text_model = data.get('text_model')
        image_model = data.get('image_model')
        
        # 验证模型是否支持
        if text_model:
            text_model_valid = False
            for model in config_manager.SUPPORTED_MODELS['text_models']:
                if model['id'] == text_model:
                    text_model_valid = True
                    break
            if not text_model_valid:
                return jsonify({'error': '不支持的文本模型'}), 400
        
        if image_model:
            image_model_valid = False
            for model in config_manager.SUPPORTED_MODELS['image_models']:
                if model['id'] == image_model:
                    image_model_valid = True
                    break
            if not image_model_valid:
                return jsonify({'error': '不支持的图像模型'}), 400
        
        # 更新配置
        success = config_manager.update_config(api_key=api_key, text_model=text_model, image_model=image_model)
        
        if success:
            log_info("配置更新成功")
            return jsonify({'success': True, 'message': '配置已成功更新'})
        else:
            log_error("配置更新失败")
            return jsonify({'error': '配置更新失败'}), 500
    except Exception as e:
        log_error(f"更新配置时出错: {str(e)}")
        return jsonify({'error': f'系统错误: {str(e)}'}), 500

@app.route('/tasks')
def get_all_tasks():
    """获取所有任务的状态"""
    try:
        tasks = {}
        for task_id, status_info in task_status.items():
            task_copy = status_info.copy()
            # 保留input_filename、processing_time和其他相关信息用于前端显示
            # 转换用时等信息已经在task_status中，这里不再需要额外处理
            tasks[task_id] = task_copy
        return jsonify(tasks)
    except Exception as e:
        temp_task_id = str(uuid.uuid4())
        log_error(f"获取任务列表时发生错误 {temp_task_id}: {str(e)}")
        return jsonify({'error': f'获取任务列表时发生错误: {str(e)}'}), 500

@app.route('/knowledge_base')
def knowledge_base():
    try:
        records_file = os.path.join('.wucai', 'processing_records.json')
        records = []
        
        if os.path.exists(records_file):
            try:
                with open(records_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:  # 检查文件内容是否为空
                        records = json.loads(content)
                    else:
                        records = []  # 空文件则初始化为空列表
            except (json.JSONDecodeError, FileNotFoundError):
                records = []  # 如果解析失败或文件不存在，初始化为空列表
        
        # 反转列表以显示最新的记录在前面
        records.reverse()
        
        return jsonify(records)
    except Exception as e:
        temp_task_id = str(uuid.uuid4())
        log_error(f"获取知识库记录时发生错误 {temp_task_id}: {str(e)}")
        return jsonify({'error': f'获取知识库记录时发生错误: {str(e)}'}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)
    except Exception as e:
        temp_task_id = str(uuid.uuid4())
        log_error(f"下载文件时发生错误 {temp_task_id} (文件: {filename}): {str(e)}")
        return f"下载文件时发生错误: {str(e)}", 500

@app.route('/view/<filename>')
def view_file(filename):
    try:
        # 注意：对于输出文件，我们不对文件名进行secure_filename处理，以支持中文文件名
        # 但我们仍然需要防止路径遍历攻击
        file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
        
        # 确保文件在正确的目录下（防止路径遍历）
        output_folder_realpath = os.path.realpath(app.config['OUTPUT_FOLDER'])
        file_realpath = os.path.realpath(file_path)
        if not file_realpath.startswith(output_folder_realpath):
            return "非法文件路径", 403
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return f"文件不存在: {filename}", 404
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        temp_task_id = str(uuid.uuid4())
        log_error(f"无法读取文件错误 {temp_task_id} (文件: {filename}): {str(e)}")
        return f"无法读取文件: {str(e)}", 500


# @app.route('/markdown_viewer')
# def markdown_viewer():
#     """Markdown文档查看器主页"""
#     return render_template('markdown_viewer.html')


@app.route('/render_markdown', methods=['POST'])
def render_markdown():
    """渲染Markdown内容为HTML"""
    try:
        data = request.json
        markdown_text = data.get('markdown', '')
        
        # 使用MarkdownRenderer进行安全渲染
        rendered_html = renderer.render(markdown_text)
        
        return jsonify({
            'success': True,
            'html': rendered_html
        })
    except Exception as e:
        temp_task_id = str(uuid.uuid4())
        log_error(f"渲染Markdown时发生错误 {temp_task_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

#
# @app.route('/view_doc/<filename>')
# def view_document(filename):
#     """查看知识库文档（带Markdown渲染）"""
#     try:
#         # 防止路径遍历攻击
#         file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
#
#         output_folder_realpath = os.path.realpath(app.config['OUTPUT_FOLDER'])
#         file_realpath = os.path.realpath(file_path)
#         if not file_realpath.startswith(output_folder_realpath):
#             return "非法文件路径", 403
#
#         if not os.path.exists(file_path):
#             return f"文件不存在: {filename}", 404
#
#         # 读取文件内容
#         with open(file_path, 'r', encoding='utf-8') as f:
#             content = f.read()
#
#         # 渲染为HTML
#         rendered_html = renderer.render(content)
#
#         # 渲染到模板中显示
#         return render_template('markdown_viewer.html',
#                              content=rendered_html,
#                              filename=filename,
#                              title=f"查看文档 - {filename}")
#     except Exception as e:
#         temp_task_id = str(uuid.uuid4())
#         log_error(f"查看文档时发生错误 {temp_task_id} (文件: {filename}): {str(e)}")
#         return f"查看文档时发生错误: {str(e)}", 500


@app.route('/error_logs')
def get_error_logs():
    """获取错误日志列表"""
    try:
        error_log_file = os.path.join('.wucai', 'error_logs.json')
        error_logs = []
        
        if os.path.exists(error_log_file):
            try:
                with open(error_log_file, 'r', encoding='utf-8') as f:
                    error_logs = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                error_logs = []
        
        # 反转列表以显示最新的记录在前面
        error_logs.reverse()
        
        return jsonify(error_logs)
    except Exception as e:
        temp_task_id = str(uuid.uuid4())
        log_error(f"获取错误日志时发生错误 {temp_task_id}: {str(e)}")
        return jsonify({'error': f'获取错误日志时发生错误: {str(e)}'}), 500


@app.route('/download_error_log')
def download_error_log():
    """下载错误日志文件"""
    try:
        error_log_file = os.path.join('.wucai', 'error_logs.json')
        
        if not os.path.exists(error_log_file):
            return "错误日志文件不存在", 404
            
        return send_from_directory(
            directory='.wucai',
            path='error_logs.json',
            as_attachment=True,
            download_name='error_logs.json'
        )
    except Exception as e:
        temp_task_id = str(uuid.uuid4())
        log_error(f"下载错误日志时发生错误 {temp_task_id}: {str(e)}")
        return f"下载错误日志时发生错误: {str(e)}", 500

@app.route('/delete_document/<filename>', methods=['DELETE'])
def delete_document(filename):
    """删除知识库文档
    从output目录删除文件，并从知识库列表中移除记录，但保留任务记录
    """
    try:
        # 防止路径遍历攻击
        file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
        output_folder_realpath = os.path.realpath(app.config['OUTPUT_FOLDER'])
        file_realpath = os.path.realpath(file_path)
        
        if not file_realpath.startswith(output_folder_realpath):
            return jsonify({'success': False, 'error': '非法文件路径'}), 403
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': '文件不存在'}), 404
        
        # 从processing_records.json中移除对应的记录
        records_file = os.path.join('.wucai', 'processing_records.json')
        records = []
        if os.path.exists(records_file):
            with open(records_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:  # 检查文件内容是否为空
                    records = json.loads(content)
                else:
                    records = []  # 空文件则初始化为空列表
        
        # 过滤掉要删除的文件记录
        # 注意：我们仍然保留任务记录，只是从知识库列表中移除
        filtered_records = [record for record in records if record.get('output_file') != filename]
        
        # 保存更新后的记录
        with open(records_file, 'w', encoding='utf-8') as f:
            json.dump(filtered_records, f, ensure_ascii=False, indent=2)
        
        # 删除物理文件
        os.remove(file_path)
        
        log_info(f"成功删除文档: {filename}")
        return jsonify({'success': True, 'message': '文档删除成功'})
    except Exception as e:
        temp_task_id = str(uuid.uuid4())
        log_error(f"删除文档时发生错误 {temp_task_id} (文件: {filename}): {str(e)}")
        return jsonify({'success': False, 'error': f'删除失败: {str(e)}'}), 500


@app.errorhandler(500)
def internal_error(error):
    """全局500错误处理器"""
    temp_task_id = str(uuid.uuid4())
    log_error(f"服务器内部错误 {temp_task_id}: {str(error)}")
    return jsonify({'error': '服务器内部错误'}), 500

@app.errorhandler(404)
def not_found(error):
    """全局404错误处理器"""
    temp_task_id = str(uuid.uuid4())
    log_error(f"资源未找到错误 {temp_task_id}: {str(error)}")
    return jsonify({'error': '请求的资源未找到'}), 404

@app.errorhandler(Exception)
def handle_exception(e):
    """全局异常处理器"""
    # 捕获所有未处理的异常
    temp_task_id = str(uuid.uuid4())
    log_error(f"未处理的异常 {temp_task_id}: {str(e)}")
    return jsonify({'error': f'发生未处理的异常: {str(e)}'}), 500

if __name__ == '__main__':
    # 修复路径中的空格问题
    # import sys
    # import os
    # if getattr(sys, 'frozen', False):
    #     # 如果是打包后的可执行文件
    #     application_path = os.path.dirname(sys.executable)
    # else:
    #     # 开发模式下，获取当前文件目录
    #     application_path = os.path.dirname(os.path.abspath(__file__))
    #
    # # 设置工作目录
    # os.chdir(application_path)
    
    # 运行应用
    app.run(debug=False, port=5000)  # 改为端口5000保持一致性