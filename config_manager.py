import os
import json
import logging
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_FILE = os.path.join('.wucai', 'config.json')

# 默认配置
DEFAULT_CONFIG = {
    'api_key': '',
    'text_model': 'qwen-plus',
    'image_model': 'qwen-vl-plus',
    'last_updated': ''
}

# 支持的模型列表
SUPPORTED_MODELS = {
    'text_models': [
        {'id': 'qwen-turbo', 'name': 'qwen-turbo', 'type': '文本', 'image_support': False, 'context_length': 32768, 
         'input_price': 0.008, 'output_price': 0.008, 'rating': 2, 'purpose': '快速响应、简单问答、高并发'},
        {'id': 'qwen-plus', 'name': 'qwen-plus', 'type': '文本', 'image_support': False, 'context_length': 128000, 
         'input_price': 0.024, 'output_price': 0.024, 'rating': 4, 'purpose': '平衡性能与成本，中等复杂任务'},
        {'id': 'qwen-max', 'name': 'qwen-max', 'type': '文本', 'image_support': False, 'context_length': 32768, 
         'input_price': 0.08, 'output_price': 0.08, 'rating': 5, 'purpose': '复杂推理、代码生成、高精度任务'},
        {'id': 'qwen-max-longcontext', 'name': 'qwen-max-longcontext', 'type': '文本', 'image_support': False, 'context_length': 327680, 
         'input_price': 0.12, 'output_price': 0.12, 'rating': 5, 'purpose': '超长文档理解、法律/金融分析'},
        {'id': 'qwen1.5-7b-chat', 'name': 'qwen1.5-7b-chat', 'type': '文本', 'image_support': False, 'context_length': 32768, 
         'input_price': 0, 'output_price': 0, 'rating': 3, 'purpose': '开源轻量级模型，本地部署'},
        {'id': 'qwen1.5-14b-chat', 'name': 'qwen1.5-14b-chat', 'type': '文本', 'image_support': False, 'context_length': 32768, 
         'input_price': 0, 'output_price': 0, 'rating': 3.5, 'purpose': '开源中等模型，平衡性能与资源'},
        {'id': 'qwen1.5-32b-chat', 'name': 'qwen1.5-32b-chat', 'type': '文本', 'image_support': False, 'context_length': 32768, 
         'input_price': 0, 'output_price': 0, 'rating': 4, 'purpose': '开源高性能模型，强推理能力'},
        {'id': 'qwen1.5-72b-chat', 'name': 'qwen1.5-72b-chat', 'type': '文本', 'image_support': False, 'context_length': 32768, 
         'input_price': 0, 'output_price': 0, 'rating': 4.5, 'purpose': '开源超大模型，接近闭源效果'},
        {'id': 'qwen2-7b-instruct', 'name': 'qwen2-7b-instruct', 'type': '文本', 'image_support': False, 'context_length': 32768, 
         'input_price': 0.01, 'output_price': 0.01, 'rating': 3.5, 'purpose': '新一代轻量模型，性价比高'},
        {'id': 'qwen2-57b-a14b-instruct', 'name': 'qwen2-57b-a14b-instruct', 'type': '文本', 'image_support': False, 'context_length': 32768, 
         'input_price': 0.05, 'output_price': 0.05, 'rating': 4.5, 'purpose': '高性能文本模型，推理能力强'},
        {'id': 'qwen2-72b-instruct', 'name': 'qwen2-72b-instruct', 'type': '文本', 'image_support': False, 'context_length': 32768, 
         'input_price': 0.06, 'output_price': 0.06, 'rating': 4.5, 'purpose': '开源最强文本模型之一，强推理'},
        {'id': 'qwen2.5-7b-instruct', 'name': 'qwen2.5-7b-instruct', 'type': '文本', 'image_support': False, 'context_length': 32768, 
         'input_price': 0.015, 'output_price': 0.015, 'rating': 3.5, 'purpose': '2.5代轻量模型，性能提升'},
        {'id': 'qwen2.5-32b-instruct', 'name': 'qwen2.5-32b-instruct', 'type': '文本', 'image_support': False, 'context_length': 32768, 
         'input_price': 0.04, 'output_price': 0.04, 'rating': 4.5, 'purpose': '2.5代中大型模型，优秀推理能力'},
        {'id': 'qwen2.5-72b-instruct', 'name': 'qwen2.5-72b-instruct', 'type': '文本', 'image_support': False, 'context_length': 32768, 
         'input_price': 0.065, 'output_price': 0.065, 'rating': 5, 'purpose': '2.5代顶级模型，顶级性能表现'}
    ],
    'image_models': [
        {'id': 'qwen-vl-plus', 'name': 'qwen-vl-plus', 'type': '多模态', 'image_support': True, 'context_length': 32768, 
         'input_price': 0.02, 'output_price': 0.02, 'rating': 4, 'purpose': '图像+文本对话，通用多模态'},
        {'id': 'qwen-vl-max', 'name': 'qwen-vl-max', 'type': '多模态', 'image_support': True, 'context_length': 32768, 
         'input_price': 0.08, 'output_price': 0.08, 'rating': 5, 'purpose': '最强多模态模型，复杂视觉推理'},
        {'id': 'qwen2-vl-7b-instruct', 'name': 'qwen2-vl-7b-instruct', 'type': '多模态', 'image_support': True, 'context_length': 32768, 
         'input_price': 0.02, 'output_price': 0.02, 'rating': 3.5, 'purpose': '轻量级多模态任务，成本敏感场景'},
        {'id': 'qwen2-vl-72b-instruct', 'name': 'qwen2-vl-72b-instruct', 'type': '多模态', 'image_support': True, 'context_length': 32768, 
         'input_price': 0.08, 'output_price': 0.08, 'rating': 5, 'purpose': '图文理解、视觉问答、多模态推理'}
    ]
}

# 推荐场景配置
RECOMMENDED_SCENARIOS = [
    {'scenario': '纯文本、高并发、低成本', 'recommended_model': 'qwen-turbo'},
    {'scenario': '纯文本、长文档（>10万字）', 'recommended_model': 'qwen-max-longcontext'},
    {'scenario': '纯文本、强推理/代码', 'recommended_model': 'qwen-max 或 qwen2-72b-instruct'},
    {'scenario': '图文问答、图像理解', 'recommended_model': 'qwen-vl-plus（性价比） 或 qwen-vl-max（高性能）'},
    {'scenario': '多模态+大模型开源可控', 'recommended_model': 'qwen2-vl-72b-instruct（适合私有部署参考）'}
]

def load_config():
    """
    从文件加载配置
    """
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 合并默认配置，确保所有必需字段存在
                return {**DEFAULT_CONFIG, **config}
        else:
            # 如果配置文件不存在，返回默认配置
            return DEFAULT_CONFIG.copy()
    except Exception as e:
        logger.error(f"加载配置文件时出错: {str(e)}")
        return DEFAULT_CONFIG.copy()

def save_config(config):
    """
    保存配置到文件
    """
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        
        # 更新最后修改时间
        config['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 保存配置
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        logger.info("配置已成功保存")
        return True
    except Exception as e:
        logger.error(f"保存配置文件时出错: {str(e)}")
        return False

def update_config(api_key=None, text_model=None, image_model=None):
    """
    更新配置
    """
    config = load_config()
    
    if api_key is not None:
        config['api_key'] = api_key
    if text_model is not None:
        config['text_model'] = text_model
    if image_model is not None:
        config['image_model'] = image_model
    
    return save_config(config)

def validate_api_key(api_key):
    """
    验证API Key格式（简单验证）
    """
    return bool(api_key and len(api_key.strip()) > 10)

def get_model_info(model_id):
    """
    根据模型ID获取模型信息
    """
    for model in SUPPORTED_MODELS['text_models'] + SUPPORTED_MODELS['image_models']:
        if model['id'] == model_id:
            return model
    return None

def get_rating_stars(rating):
    """
    将评分转换为星星表示
    """
    full_stars = int(rating)
    half_star = rating - full_stars >= 0.5
    empty_stars = 5 - full_stars - (1 if half_star else 0)
    
    stars = '★' * full_stars
    if half_star:
        stars += '☆'  # 使用☆表示半星
    stars += '☆' * empty_stars
    
    return stars