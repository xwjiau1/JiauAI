/**
 * Markdown渲染器
 * 负责在前端渲染Markdown内容
 */
class MarkdownViewer {
    constructor() {
        this.marked = null;
        this.isInitialized = false;
    }

    /**
     * 初始化渲染器
     */
    async init() {
        if (this.isInitialized) {
            return;
        }

        // 动态加载marked.js库
        if (typeof marked === 'undefined') {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/marked/marked.min.js';
            document.head.appendChild(script);

            // 等待marked库加载完成
            await new Promise((resolve) => {
                script.onload = resolve;
            });
        }

        // 动态加载highlight.js库
        if (typeof hljs === 'undefined') {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/default.min.css';
            document.head.appendChild(link);

            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js';
            document.head.appendChild(script);

            // 等待highlight.js库加载完成
            await new Promise((resolve) => {
                script.onload = resolve;
            });
        }

        // 配置marked
        marked.setOptions({
            gfm: true,
            breaks: true,
            smartLists: true,
            smartypants: true,
            highlight: function(code, lang) {
                if (lang && hljs.getLanguage(lang)) {
                    try {
                        return hljs.highlight(code, { language: lang }).value;
                    } catch (e) {
                        console.warn('Highlight.js error:', e);
                    }
                }
                return code;
            }
        });

        this.isInitialized = true;
    }

    /**
     * 渲染Markdown内容到指定元素
     * @param {string} markdown - Markdown文本
     * @param {HTMLElement} targetElement - 目标元素
     */
    async render(markdown, targetElement) {
        if (!this.isInitialized) {
            await this.init();
        }

        // 转义HTML特殊字符以防止XSS
        const escapedMarkdown = this.escapeHtml(markdown);
        
        // 渲染Markdown为HTML
        let html = marked.parse(escapedMarkdown);

        // 设置内容到目标元素
        targetElement.innerHTML = html;

        // 执行代码高亮
        this.highlightCodeBlocks(targetElement);

        // 处理链接，使其在新窗口打开
        this.processLinks(targetElement);

        // 处理图片，添加响应式样式
        this.processImages(targetElement);
    }

    /**
     * 转义HTML特殊字符
     * @param {string} text - 要转义的文本
     * @return {string} 转义后的文本
     */
    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };

        return text.replace(/[&<>"']/g, m => map[m]);
    }

    /**
     * 高亮代码块
     * @param {HTMLElement} container - 包含代码块的容器元素
     */
    highlightCodeBlocks(container) {
        if (typeof hljs !== 'undefined') {
            container.querySelectorAll('pre code').forEach(block => {
                hljs.highlightElement(block);
            });
        }
    }

    /**
     * 处理链接，设置在新窗口打开
     * @param {HTMLElement} container - 包含链接的容器元素
     */
    processLinks(container) {
        container.querySelectorAll('a').forEach(link => {
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
        });
    }

    /**
     * 处理图片，添加响应式样式
     * @param {HTMLElement} container - 包含图片的容器元素
     */
    processImages(container) {
        container.querySelectorAll('img').forEach(img => {
            img.classList.add('img-responsive');
            img.style.maxWidth = '100%';
            img.style.height = 'auto';
        });
    }
}

// 创建全局Markdown查看器实例
const markdownViewer = new MarkdownViewer();