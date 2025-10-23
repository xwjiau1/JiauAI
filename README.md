# 文档转知识库工具

这是一个功能强大的文档转知识库工具，可以将PDF、PPT/PPTX、Markdown文件通过大模型API转换为结构化的Markdown文档，适合作为个人知识库使用。该工具不仅支持文本提取和处理，还能识别文档中的图片内容，提供完整的文档理解方案。

## 功能特点

### 核心转换功能
- 支持PDF文件内容提取与结构化转换
- 支持PPT/PPTX文件解析，包括文本和图片提取
- 支持Markdown文件内容处理和增强
- 通过大模型API整理和格式化内容
- 支持自定义提示词进行个性化处理

### 图像处理能力
- 自动提取文档中的图片
- 使用视觉大模型识别图片内容
- 将图片描述整合到Markdown文档中
- 支持本地和远程图片的处理

### Web界面功能
- 提供直观的文件上传界面
- 任务队列管理和状态实时跟踪
- 处理进度可视化显示
- 转换结果在线查看和下载
- 历史任务记录管理

### 高级特性
- 完整的token用量统计（文本处理+图像识别）
- 详细的错误日志记录和分析
- 任务状态持久化存储
- 支持大文件处理（最大200MB）
- 支持中文文件名和内容

## 安装依赖

### 基本依赖
```bash
pip install -r requirements.txt
```

### 可选依赖
处理PPT文件时会自动尝试安装python-pptx，也可以手动安装：
```bash
pip install python-pptx>=0.6.23
```

## 配置

### API密钥配置
工具使用DashScope API，需要配置有效的API密钥。您可以通过以下方式提供API密钥（优先级从高到低）：

1. Web界面中直接输入
2. 命令行参数 `--api-key` 或 `--app-key`
3. 环境变量 `DASHSCOPE_API_KEY`
4. 配置文件 `.wucai/config.json` 中的 `app_key`

### 配置文件
默认配置文件位于 `.wucai/config.json`，支持以下配置项：

```json
{
  "app_key": "your_dashscope_api_key",
  "model_endpoint": "api_endpoint_url",
  "default_prompt": "请将以下内容整理为结构化的Markdown文档，保留关键信息和逻辑结构",
  "output_dir": "output"
}
```

### Windows系统设置
在Windows系统中，可以通过以下方式设置环境变量：

1. 命令行临时设置：
   ```cmd
   set DASHSCOPE_API_KEY=your_api_key_here
   ```

2. 系统设置永久设置：
   - 打开"系统属性" -> "高级" -> "环境变量"
   - 在"用户变量"或"系统变量"中添加新的变量
   - 变量名: `DASHSCOPE_API_KEY`
   - 变量值: 您的API密钥

## 使用方法

### 命令行使用

#### 基本用法
```bash
python pdf_to_knowledge_md.py /path/to/your/file.pdf
```

#### 使用自定义提示词
```bash
python pdf_to_knowledge_md.py /path/to/your/file.pdf --prompt "请重点提取关键技术点和实施方法"
```

#### 指定输出路径
```bash
python pdf_to_knowledge_md.py /path/to/your/file.pdf --output /path/to/output.md
```

#### 使用自定义API密钥
```bash
python pdf_to_knowledge_md.py /path/to/your/file.pdf --api-key "your_api_key_here"
```

### Web界面使用

#### 启动Web服务
```bash
python web_app.py
```

服务默认在 http://localhost:5004 启动

#### 使用步骤
1. 打开浏览器访问 http://localhost:5004
2. 在页面中上传支持的文件类型（PDF、PPT、PPTX、MD）
3. 输入您的DashScope API密钥
4. 可选：输入自定义提示词以指导内容处理
5. 点击"开始处理"按钮提交任务
6. 查看任务处理进度和状态
7. 处理完成后，可以在线查看或下载转换后的Markdown文档

## 支持的文件格式

- PDF (.pdf)
- PowerPoint (.ppt, .pptx)
- Markdown (.md, .markdown)

## 工作原理

### 命令行工作流程
1. 读取并解析输入文件
2. 提取文本内容（对于PPT/PPTX还会提取图片）
3. 通过DashScope API处理文本内容
4. 对于包含图片的文件，调用视觉模型识别图片内容
5. 整合处理结果，生成结构化Markdown文档
6. 保存输出文件并显示token用量统计

### Web应用工作流程
1. 用户上传文件并提供必要参数
2. 系统生成唯一任务ID并创建任务记录
3. 任务被添加到处理队列
4. 后台工作线程处理任务
5. 实时更新任务状态和进度
6. 处理完成后存储结果文件并更新任务记录
7. 用户可以查询状态、查看或下载结果

## 日志与记录

### 运行日志
- 按日期记录在 `run-log/` 目录下
- 包含详细的操作记录和错误信息

### 错误日志
- 保存在 `.wucai/error_logs.json`
- 包含完整的错误详情和堆栈跟踪
- 可通过Web界面查看和下载

### 处理记录
- 保存在 `.wucai/processing_records.json`
- 记录所有处理任务的详细信息
- 包括处理时间、token用量、输出长度等统计信息

## 注意事项

1. 确保已配置有效的DashScope API密钥
2. 对于较长或包含大量图片的文件，API调用可能需要较长时间
3. 处理超时设置为5分钟，超大文件可能需要优化或分段处理
4. 确保网络连接稳定，以便成功调用API
5. 大模型API调用会消耗token，请注意您的API配额和费用

## 性能与限制

- 文件大小上限：200MB
- 处理超时：5分钟
- 错误日志保留最新1000条记录
- 支持Windows、Linux和macOS系统

## 故障排除

### 常见问题

1. **API密钥错误**：确保输入的DashScope API密钥有效
2. **处理超时**：对于大型文件，可能需要分段处理或增加超时时间
3. **图片识别失败**：检查网络连接和API配额
4. **文件格式不支持**：确认文件扩展名在支持的列表中

### 错误排查

1. 查看运行日志获取详细错误信息
2. 通过Web界面查看错误日志
3. 检查API密钥是否正确配置
4. 确认网络连接是否正常

## 开发与扩展

### 项目结构
```
├── web_app.py         # Web应用主文件
├── pdf_to_knowledge_md.py # 核心转换功能
├── templates/         # Web模板
├── uploads/           # 上传文件存储
├── output/            # 输出文件存储
├── .wucai/            # 配置和记录文件
├── run-log/           # 运行日志
└── requirements.txt   # 依赖列表
```

### 自定义扩展
- 可以修改默认提示词以适应不同的内容处理需求
- 支持调整任务队列和工作线程配置
- 可以扩展支持更多文件格式

## 许可证

该项目为内部工具，仅供授权使用。

## 联系方式

如有问题或建议，请联系项目维护团队。