"""
Markdown渲染工具类
提供安全的Markdown到HTML转换功能
"""
import markdown2
import bleach
from typing import Optional


class MarkdownRenderer:
    """
    Markdown渲染器，负责将Markdown文本安全地转换为HTML
    """
    
    def __init__(self):
        # 定义允许的HTML标签
        self.allowed_tags = [
            'p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'strong', 'em', 'u', 'del', 'code', 'pre', 'blockquote',
            'ul', 'ol', 'li', 'dl', 'dt', 'dd',
            'a', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
            'div', 'span', 'hr'
        ]
        
        # 定义允许的HTML属性
        self.allowed_attributes = {
            'a': ['href', 'title', 'target'],
            'img': ['src', 'alt', 'title', 'width', 'height'],
            'code': ['class'],
            'pre': ['class'],
            'div': ['class'],
            'span': ['class'],
            'h1': ['id', 'class'],
            'h2': ['id', 'class'],
            'h3': ['id', 'class'],
            'h4': ['id', 'class'],
            'h5': ['id', 'class'],
            'h6': ['id', 'class'],
            'td': ['align'],
            'th': ['align']
        }
        
        # 定义允许的CSS类
        self.allowed_styles = []

    def render(self, markdown_text: str) -> str:
        """
        将Markdown文本转换为安全的HTML
        
        Args:
            markdown_text: 输入的Markdown文本
            
        Returns:
            渲染后的HTML字符串
        """
        if not markdown_text:
            return ""
        
        # 首先使用markdown2将Markdown转换为HTML
        html = markdown2.markdown(
            markdown_text,
            extras=[
                'fenced-code-blocks',
                'tables',
                'strike',
                'task_list',
                'code-friendly',
                'cuddled-lists'
            ]
        )
        
        # 使用bleach清理HTML，防止XSS攻击
        # 注意：某些bleach版本不支持styles参数
        try:
            clean_html = bleach.clean(
                html,
                tags=self.allowed_tags,
                attributes=self.allowed_attributes,
                styles=self.allowed_styles,
                strip=True
            )
        except TypeError:
            # 如果styles参数不被支持，则不使用它
            clean_html = bleach.clean(
                html,
                tags=self.allowed_tags,
                attributes=self.allowed_attributes,
                strip=True
            )
        
        return clean_html


# 创建全局渲染器实例
renderer = MarkdownRenderer()