import os
import json
import dashscope
from dashscope.api_entities.dashscope_response import Role
from PyPDF2 import PdfReader
import argparse
import sys
from pathlib import Path
import re
from dashscope import MultiModalConversation
import tempfile
from datetime import datetime
import traceback
import logging

# 从环境变量获取配置
TEXT_MODEL = os.environ.get('TEXT_MODEL', 'qwen-plus')
IMAGE_MODEL = os.environ.get('IMAGE_MODEL', 'qwen-vl-plus')
DASHSCOPE_API_KEY = os.environ.get('DASHSCOPE_API_KEY', '')

# 创建运行日志目录 - 按日期创建日志文件
today = datetime.now().strftime('%Y%m%d')
log_dir = "run-log"
os.makedirs(log_dir, exist_ok=True)

# 配置日志 - 按天记录到同一天的日志文件
log_filename = f"{log_dir}/{today}.log"

# 为Windows系统设置控制台编码
try:
    if sys.platform.startswith('win'):
        # 设置控制台编码为UTF-8
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)  # 设置控制台输入编码为UTF-8
        kernel32.SetConsoleOutputCP(65001)  # 设置控制台输出编码为UTF-8
        
        # 同时设置标准输出和标准错误的编码
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
except Exception as e:
    print(f"设置控制台编码时出错: {str(e)}")

# 自定义StreamHandler类来处理编码问题
class UnicodeStreamHandler(logging.StreamHandler):
    def __init__(self, stream=None):
        super().__init__(stream)
        self.encoding = 'utf-8'
    
    def emit(self, record):
        try:
            # 确保消息是UTF-8编码的字符串
            msg = self.format(record)
            if isinstance(msg, str):
                msg = msg.encode('utf-8', errors='replace').decode('utf-8')
            
            stream = self.stream
            stream.write(msg)
            stream.write(self.terminator)
            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        UnicodeStreamHandler()  # 使用自定义的StreamHandler
    ],
    force=True  # 强制重新配置日志系统
)

logger = logging.getLogger(__name__)

def log_info(message):
    """记录信息日志"""
    logger.info(message)

def log_error(message):
    """记录错误日志"""
    logger.error(message)

def log_debug(message):
    """记录调试日志"""
    logger.debug(message)

def read_pdf(file_path):
    """
    读取PDF文件内容
    """
    try:
        log_info(f"开始读取PDF文件: {file_path}")
        reader = PdfReader(file_path)
        text_content = ""
        for page in reader.pages:
            text_content += page.extract_text() + "\n"
        log_info(f"PDF文件读取完成，总字符数: {len(text_content)}")
        return text_content
    except Exception as e:
        error_msg = f"读取PDF文件时出错: {str(e)}"
        log_error(error_msg)
        log_error(f"详细错误信息: {traceback.format_exc()}")
        return None

def read_markdown(file_path):
    """
    读取markdown文件内容
    """
    try:
        log_info(f"开始读取markdown文件: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        log_info(f"markdown文件读取完成，总字符数: {len(content)}")
        return content
    except Exception as e:
        error_msg = f"读取markdown文件时出错: {str(e)}"
        log_error(error_msg)
        log_error(f"详细错误信息: {traceback.format_exc()}")
        return None

def read_ppt(file_path):
    """
    读取PPT文件内容，提取文本和图片
    """
    try:
        log_info(f"开始读取PPT文件: {file_path}")
        
        # 先检查pptx模块是否已安装
        try:
            import pptx
            log_info(f"python-pptx模块已安装，版本: {pptx.__version__}")
        except ImportError:
            log_error("python-pptx模块未安装，尝试自动安装...")
            try:
                # 尝试自动安装依赖
                import subprocess
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'python-pptx>=0.6.23'])
                log_info("python-pptx模块安装成功")
            except Exception as install_error:
                log_error(f"自动安装python-pptx失败: {str(install_error)}")
                log_error("请手动运行: pip install python-pptx>=0.6.23")
                raise ImportError("缺少python-pptx依赖，请安装: pip install python-pptx>=0.6.23")
        
        from pptx import Presentation
        from pptx.enum.shapes import MSO_SHAPE_TYPE
        import os
        
        prs = Presentation(file_path)
        content = {"slides": [], "images": []}
        
        for i, slide in enumerate(prs.slides):
            slide_content = {
                "slide_number": i + 1,
                "text": [],
                "images": []
            }
            
            # 提取文本
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_content["text"].append(shape.text)
                elif shape.shape_type == MSO_SHAPE_TYPE.PLACEHOLDER:
                    if hasattr(shape, "text_frame") and shape.text_frame:
                        text = ""
                        for paragraph in shape.text_frame.paragraphs:
                            text += "".join(run.text for run in paragraph.runs)
                        if text.strip():
                            slide_content["text"].append(text)
            
            # 提取图片
            for shape in slide.shapes:
                if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    image = shape.image
                    # 保存图片到临时文件
                    image_filename = f"slide_{i+1}_image_{len(slide_content['images'])+1}.png"
                    image_path = os.path.join(tempfile.gettempdir(), image_filename)
                    with open(image_path, "wb") as f:
                        f.write(image.blob)
                    slide_content["images"].append(image_path)
                    content["images"].append(image_path)
            
            content["slides"].append(slide_content)
        
        log_info(f"PPT文件读取完成，共 {len(content['slides'])} 张幻灯片")
        return content
    except ImportError as e:
        # 专门处理模块未找到的情况
        error_msg = f"读取PPT文件时缺少依赖: {str(e)}"
        log_error(error_msg)
        log_error("请运行: pip install python-pptx")
        raise ImportError(error_msg) from e  # 重新抛出异常以确保被外层捕获
    except Exception as e:
        error_msg = f"读取PPT文件时出错: {str(e)}"
        log_error(error_msg)
        log_error(f"详细错误信息: {traceback.format_exc()}")
        raise Exception(error_msg) from e  # 重新抛出异常以确保被外层捕获

def format_ppt_content_for_markdown(ppt_content):
    """
    将PPT内容格式化为markdown格式
    """
    log_info("开始格式化PPT内容为markdown格式")
    md_content = f"# PPT内容整理\n\n"
    md_content += f"总共 {len(ppt_content['slides'])} 张幻灯片\n\n"
    
    for slide in ppt_content["slides"]:
        md_content += f"## 第 {slide['slide_number']} 张幻灯片\n\n"
        
        for text in slide["text"]:
            if text.strip():
                md_content += f"{text}\n\n"
        
        for img_path in slide["images"]:
            img_name = os.path.basename(img_path)
            md_content += f"![{img_name}]({img_path})\n\n"
    
    log_info(f"PPT内容格式化完成，总字符数: {len(md_content)}")
    return md_content

def extract_images_from_markdown(markdown_content, base_path):
    """
    从markdown内容中提取图片路径
    """
    log_info("开始从markdown内容中提取图片路径")
    # 匹配markdown中的图片语法 ![alt text](image_path)
    image_pattern = r'!\[.*?\]\((.*?)\)'
    matches = re.findall(image_pattern, markdown_content)
    
    image_paths = []
    for match in matches:
        # 处理相对路径和绝对路径
        if match.startswith('http://') or match.startswith('https://'):
            # 远程图片URL
            image_paths.append(match)
        else:
            # 本地图片路径，转换为绝对路径
            img_path = Path(base_path).parent / match
            if img_path.exists():
                image_paths.append(str(img_path.resolve()))
            else:
                warning_msg = f"警告: 图片文件不存在 - {img_path}"
                log_info(warning_msg)
    
    log_info(f"提取到 {len(image_paths)} 个图片路径")
    return image_paths

def recognize_image_with_dashscope(api_key, image_path, custom_prompt="请详细描述这张图片的内容"):
    """
    使用DashScope视觉模型识别图片
    """
    log_info(f"开始识别图片: {image_path}")
    log_info(f"使用提示词: {custom_prompt}")
    dashscope.api_key = api_key
    
    try:
        # 构建消息，包含图片和描述请求
        if image_path.startswith('http://') or image_path.startswith('https://'):
            # 远程图片URL
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"image": image_path},
                        {"text": custom_prompt}
                    ]
                }
            ]
        else:
            # 本地图片文件
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"image": f"file://{image_path}"},
                        {"text": custom_prompt}
                    ]
                }
            ]
        
        log_info(f"调用DashScope视觉模型API...")
        
        # 使用配置的图像模型
        response = MultiModalConversation.call(
            model=IMAGE_MODEL,
            messages=messages
        )
        
        log_info(f"API响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            # 提取识别结果
            result = response.output.choices[0].message.content
            log_info(f"图片识别API调用成功")
            log_debug(f"API响应内容: {result}")
            
            # 提取并统计token用量
            image_tokens = 0
            if hasattr(response, 'usage') and response.usage:
                input_tokens = response.usage.get('input_tokens', 0)
                output_tokens = response.usage.get('output_tokens', 0)
                image_tokens = input_tokens + output_tokens
                log_info(f"图片识别Token用量统计: 输入{input_tokens} + 输出{output_tokens} = 总计{image_tokens}")
            else:
                log_info("未在图像识别API响应中找到token用量信息")
            
            # 输出图片识别的token用量，以便累加统计
            print(f"IMAGE_TOKEN_USAGE:{image_tokens}")
            
            # 处理返回的多模态内容
            if isinstance(result, list):
                for item in result:
                    if item.get('type') == 'text':
                        log_info(f"图片识别结果(文本): {item.get('text', '')[:100]}...")  # 只记录前100个字符
                        return item.get('text', '')
            elif isinstance(result, str):
                log_info(f"图片识别结果: {result[:100]}...")  # 只记录前100个字符
                return result
            else:
                result_str = str(result)
                log_info(f"图片识别结果: {result_str[:100]}...")  # 只记录前100个字符
                return result_str
        else:
            error_msg = f"图像识别API调用失败: {response.code} - {response.message}"
            log_error(error_msg)
            return None
    except Exception as e:
        error_msg = f"图像识别时出错: {str(e)}"
        log_error(error_msg)
        log_error(f"详细错误信息: {traceback.format_exc()}")
        return None

def process_markdown_with_images(api_key, markdown_content, base_path, user_prompt, config):
    """
    处理包含图片的markdown文件，对图片进行识别并整合内容
    """
    log_info("开始处理markdown文件中的图片...")
    log_info(f"用户提示词: {user_prompt}")
    
    # 提取图片路径
    image_paths = extract_images_from_markdown(markdown_content, base_path)
    
    # 存储图片识别结果
    image_descriptions = {}
    
    # 对每张图片进行识别
    for img_path in image_paths:
        log_info(f"正在识别图片: {img_path}")
        description = recognize_image_with_dashscope(
            api_key, 
            img_path, 
            "请详细描述这张图片的内容，包括其中的关键信息、文字、数据或其他重要元素。"
        )
        if description:
            image_descriptions[img_path] = description
            log_info(f"图片识别完成: {img_path}")
        else:
            log_error(f"图片识别失败: {img_path}")
    
    # 将图片描述整合到原始markdown内容中
    enhanced_content = markdown_content
    
    for img_path, description in image_descriptions.items():
        # 在图片下方添加描述
        image_ref = f"!["
        # 找到图片引用的位置并添加描述
        if img_path.startswith('http'):
            # 处理URL图片
            image_tag = f"!["
            pattern = r'!\[.*?\]\(' + re.escape(img_path) + r'\)'
        else:
            # 处理本地图片
            original_img_path = Path(img_path).name
            pattern = r'!\[.*?\][^)]*' + re.escape(original_img_path) + r'[^)]*\)'
        
        # 替换markdown，添加图片描述
        enhanced_content = re.sub(
            pattern, 
            f'![图示]({img_path})\n\n**图片描述**: {description}\n\n', 
            enhanced_content
        )
    
    # 如果没有图片，直接返回原始内容
    if not image_paths:
        # 仍然返回原始内容，但告知用户没有找到图片
        log_info("未在markdown中找到图片")
        return markdown_content
    else:
        log_info("markdown图片处理完成")
        return enhanced_content

def call_dashscope_api(api_key, content, user_prompt, config, file_type="pdf"):
    """
    调用DashScope API处理内容
    """
    log_info(f"开始调用DashScope API处理{file_type}内容...")
    log_info(f"内容长度: {len(content)} 字符")
    log_info(f"用户提示词: {user_prompt}")
    
    dashscope.api_key = api_key
    
    # 根据文件类型调整提示词
    if file_type == "markdown":
        default_prompt = config.get("default_markdown_prompt", 
                                   "请将以下markdown内容整理成适合作为个人知识库的格式，要求结构清晰，保留原有格式，并将图片描述整合到内容中，便于阅读和后续查阅。")
    elif file_type == "ppt":
        default_prompt = config.get("default_ppt_prompt", 
                                   "请将以下PPT内容整理成适合作为个人知识库的格式，要求保留幻灯片结构，提取关键知识点，并将图片内容整合到相应位置，便于阅读和后续查阅。")
    else:
        default_prompt = config.get("default_prompt", 
                                   "请将以下内容整理成适合作为个人知识库的markdown格式文档，要求结构清晰，便于阅读和后续查阅。")
    
    full_prompt = f"{default_prompt}\n\n额外要求: {user_prompt}\n\n内容如下:\n\n{content}"
    
    log_info(f"构建的完整提示词长度: {len(full_prompt)} 字符")
    log_debug(f"完整提示词内容: {full_prompt[:500]}...")  # 只记录前500个字符
    
    messages = [
        {"role": "system", "content": "你是一个专业的文档处理助手，擅长将各种内容整理成结构化markdown格式文档"},
        {"role": "user", "content": full_prompt}
    ]
    
    # 初始化token用量
    total_tokens = 0
    
    try:
        response = dashscope.Generation.call(
            model=TEXT_MODEL,
            messages=messages,
            result_format='message'
        )
        
        log_info(f"API响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.output.choices[0].message.content
            log_info(f"API调用成功，返回内容长度: {len(result) if result else 0} 字符")
            log_debug(f"API返回内容: {result[:500] if result else 'None'}...")  # 只记录前500个字符
            
            # 提取token用量信息
            if hasattr(response, 'usage') and response.usage:
                input_tokens = response.usage.get('input_tokens', 0)
                output_tokens = response.usage.get('output_tokens', 0)
                total_tokens = input_tokens + output_tokens
                log_info(f"Token用量统计: 输入{input_tokens} + 输出{output_tokens} = 总计{total_tokens}")
            else:
                log_info("未在API响应中找到token用量信息")
                
            # 输出token用量，以便web_app.py捕获
            print(f"TOKEN_USAGE:{total_tokens}")
            
            return result
        else:
            error_msg = f"API调用失败: {response.code} - {response.message}"
            log_error(error_msg)
            return None
    except Exception as e:
        error_msg = f"API调用时出错: {str(e)}"
        log_error(error_msg)
        log_error(f"详细错误信息: {traceback.format_exc()}")
        return None

def process_ppt_with_images(api_key, content, base_path, user_prompt, config):
    """
    处理PPT中的图片，对图片进行识别并整合内容
    """
    log_info("开始处理PPT内容中的图片...")
    log_info(f"用户提示词: {user_prompt}")
    
    # 提取图片路径（从markdown格式的图片语法中提取）
    image_paths = extract_images_from_markdown(content, base_path)
    
    # 存储图片识别结果
    image_descriptions = {}
    
    # 对每张图片进行识别
    for img_path in image_paths:
        log_info(f"正在识别图片: {img_path}")
        description = recognize_image_with_dashscope(
            api_key, 
            img_path, 
            "请详细描述这张图片的内容，包括其中的关键信息、文字、数据或其他重要元素。"
        )
        if description:
            image_descriptions[img_path] = description
            log_info(f"图片识别完成: {img_path}")
        else:
            log_error(f"图片识别失败: {img_path}")
    
    # 将图片描述整合到原始内容中
    enhanced_content = content
    
    for img_path, description in image_descriptions.items():
        # 使用正则表达式找到图片引用并添加描述
        original_img_path = Path(img_path).name
        pattern = r'!\[.*?\][^)]*' + re.escape(original_img_path) + r'[^)]*\)'
        
        # 替换markdown，添加图片描述
        enhanced_content = re.sub(
            pattern, 
            f'![图示]({img_path})\n\n**图片描述**: {description}\n\n', 
            enhanced_content
        )
    
    # 如果没有图片，直接返回原始内容
    if not image_paths:
        log_info("未在PPT内容中找到图片")
        return content
    else:
        log_info("PPT图片处理完成")
        return enhanced_content

def save_markdown(content, output_path):
    """
    保存内容到markdown文件
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        log_info(f"文档已保存到: {output_path}")
        return True
    except Exception as e:
        error_msg = f"保存文件时出错: {str(e)}"
        log_error(error_msg)
        log_error(f"详细错误信息: {traceback.format_exc()}")
        return False

def load_config():
    """
    从配置文件加载配置
    """
    log_info("加载配置文件...")
    config_path = ".wucai/config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:  # 检查文件内容是否为空
                    config = json.loads(content)
                    log_info("配置文件加载成功")
                    return config
                else:
                    log_info("配置文件为空，使用默认配置")
                    return {}
        except (json.JSONDecodeError, FileNotFoundError) as e:
            log_error(f"配置文件读取错误: {str(e)}，使用默认配置")
            return {}
    else:
        # 创建默认配置
        default_config = {
            "app_key": "",
            "default_prompt": "请将以下PDF内容整理成适合作为个人知识库的markdown格式文档，要求结构清晰，便于阅读和后续查阅。",
            "default_markdown_prompt": "请将以下markdown内容整理成适作为个人知识库的格式，要求结构清晰，保留原有格式，并将图片描述整合到内容中，便于阅读和后续查阅。",
            "default_ppt_prompt": "请将以下PPT内容整理成适合作为个人知识库的格式，要求保留幻灯片结构，提取关键知识点，并将图片内容整合到相应位置，便于阅读和后续查阅。",
            "output_dir": "./output"
        }
        os.makedirs(".wucai", exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        log_info("创建默认配置文件")
        return default_config

def main():
    try:
        log_info("开始执行PDF转知识库程序")
        
        parser = argparse.ArgumentParser(description='将PDF、PPT或markdown文件通过大模型API转换为格式化的知识库文档')
        parser.add_argument('input_path', help='输入文件路径(PDF、PPT或markdown)')
        parser.add_argument('--prompt', '-p', default='', help='额外的个性化提示词')
        parser.add_argument('--output', '-o', help='输出文件路径')
        parser.add_argument('--api-key', help='DashScope API Key')
        
        args = parser.parse_args()
        
        log_info(f"输入参数: input_path={args.input_path}, prompt={args.prompt}, output={args.output}")
        
        # 检查输入文件是否存在
        if not os.path.exists(args.input_path):
            error_msg = f"错误: 输入文件不存在 - {args.input_path}"
            log_error(error_msg)
            sys.exit(1)
        
        # 判断文件类型
        file_ext = Path(args.input_path).suffix.lower()
        if file_ext not in ['.pdf', '.md', '.markdown', '.ppt', '.pptx']:
            error_msg = f"错误: 不支持的文件格式 - {file_ext}. 支持的格式: PDF, MD, MARKDOWN, PPT, PPTX"
            log_error(error_msg)
            sys.exit(1)
        
        log_info(f"处理文件类型: {file_ext}")
        
        # 加载配置
        config = load_config()
        
        # 获取API KEY，优先级：命令行参数 > 全局环境变量 > 环境变量 > 配置文件
        api_key = args.api_key or DASHSCOPE_API_KEY or os.getenv('DASHSCOPE_API_KEY') or config.get("app_key", "")
        
        if not api_key:
            error_msg = "错误: 未提供API KEY，请设置环境变量DASHSCOPE_API_KEY，或使用 --api-key 参数，或在配置文件中设置"
            log_error(error_msg)
            sys.exit(1)
        
        log_info("API KEY已验证")
        
        # 根据文件类型处理内容
        if file_ext in ['.pdf']:
            # PDF处理
            log_info("开始处理PDF文件...")
            content = read_pdf(args.input_path)
            file_type = "pdf"
        elif file_ext in ['.md', '.markdown']:
            # Markdown处理
            log_info("开始处理markdown文件...")
            content = read_markdown(args.input_path)
            if content:
                # 处理markdown中的图片
                log_info("处理markdown中的图片...")
                content = process_markdown_with_images(api_key, content, args.input_path, args.prompt, config)
            file_type = "markdown"
        elif file_ext in ['.ppt', '.pptx']:
            # PPT处理
            log_info("开始处理PPT文件...")
            content = read_ppt(args.input_path)
            if content:
                # 格式化PPT内容为markdown
                content = format_ppt_content_for_markdown(content)
                # 处理PPT中的图片
                log_info("处理PPT中的图片...")
                content = process_ppt_with_images(api_key, content, args.input_path, args.prompt, config)
            file_type = "ppt"
        
        if not content:
            error_msg = "错误: 无法读取文件内容"
            log_error(error_msg)
            sys.exit(1)
        
        log_info(f"文件内容读取成功，总字符数: {len(content)}")
        
        # 如果内容过长，进行分段处理提示
        if len(content) > 30000:  # 模型输入限制调整
            log_info("警告: 内容较长，可能超出API限制，正在发送请求...")
        
        # 调用API处理内容
        log_info("正在调用大模型API处理内容...")
        result = call_dashscope_api(api_key, content, args.prompt, config, file_type)
        
        if not result:
            error_msg = "错误: API调用失败，无法生成markdown文档"
            log_error(error_msg)
            sys.exit(1)
        
        # 确定输出路径
        if args.output:
            output_path = args.output
        else:
            # 默认输出路径为输入文件名+processed.md后缀，存放在配置的输出目录
            # 修复：确保中文文件名正确处理
            input_name = os.path.splitext(os.path.basename(args.input_path))[0]
            output_dir = config.get("output_dir", "./output")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{input_name}_processed.md")
        
        log_info(f"输出文件路径: {output_path}")
        
        # 保存结果
        if save_markdown(result, output_path):
            log_info("处理完成！")
        else:
            error_msg = "保存文件失败"
            log_error(error_msg)
            sys.exit(1)
    except Exception as e:
        error_msg = f"处理过程中发生未捕获的异常: {str(e)}"
        log_error(error_msg)
        log_error(f"详细错误信息: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()