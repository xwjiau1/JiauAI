// 任务管理功能脚本

// 根据任务状态获取状态文本
function getStatusText(status) {
    const statusMap = {
        'pending': '等待中',
        'processing': '处理中',
        'completed': '已完成',
        'failed': '失败'
    };
    return statusMap[status] || status;
}

// 加载任务列表，分离进行中和已完成的任务
function loadTasks() {
    // 检查DOM元素是否存在
    const activeTasksList = document.getElementById('activeTasksList');
    const completedTasksList = document.getElementById('completedTasksList');
    
    // 如果元素不存在，直接返回
    if (!activeTasksList || !completedTasksList) {
        console.warn('Task list elements not found. Skipping task loading.');
        return;
    }
    
    fetch('/tasks')
    .then(response => response.json())
    .then(data => {
        // 分离进行中和已完成的任务
        const activeTasks = {};
        const completedTasks = {};
        
        for (const taskId in data) {
            const task = data[taskId];
            if (task.status === 'pending' || task.status === 'processing') {
                activeTasks[taskId] = task;
            } else {
                completedTasks[taskId] = task;
            }
        }
        
        // 渲染进行中任务
        if (Object.keys(activeTasks).length === 0) {
            activeTasksList.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="fas fa-clock fa-2x mb-2"></i>
                    <p>暂无进行中的任务</p>
                </div>
            `;
        } else {
            let activeHtml = '';
            for (const taskId in activeTasks) {
                const task = activeTasks[taskId];
                activeHtml += `
                    <div class="task-item status-${task.status}">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="mb-1">
                                    ${(task.input_filenames && Array.isArray(task.input_filenames) && task.input_filenames.length > 1) 
                                        ? `批量处理: ${task.input_filenames.length} 个文件` 
                                        : (task.input_filenames && task.input_filenames.length === 1 ? task.input_filenames[0] : (task.input_filename || (taskId.substring(0, 8) + '...')))}
                                </h6>
                                <small class="text-muted">状态: ${getStatusText(task.status)}</small>
                                ${(task.input_filenames && Array.isArray(task.input_filenames) && task.input_filenames.length > 1) 
                                    ? `<div class="mt-1">
                                        <small class="text-muted">
                                            文件列表: ${task.input_filenames.slice(0, 3).join(', ')}${task.input_filenames.length > 3 ? ` 等${task.input_filenames.length}个文件` : ''}
                                        </small>
                                    </div>` 
                                    : ''}
                            </div>
                            <div>
                                <span class="badge bg-secondary">${Math.round(task.progress || 0)}%</span>
                            </div>
                        </div>
                        <div class="mt-2">
                            <div class="progress">
                                <div class="progress-bar" role="progressbar" style="width: ${task.progress || 0}%">
                                    ${Math.round(task.progress || 0)}%
                                </div>
                            </div>
                        </div>
                        
                        ${task.start_time ? `<div class="mt-1"><small class="text-muted">开始时间: ${new Date(task.start_time * 1000).toLocaleString()}</small></div>` : ''}
                        ${task.token_usage ? `<div class="mt-1"><small class="text-muted">Token用量: ${task.token_usage}</small></div>` : ''}
                        ${task.processing_time ? `<div class="mt-1"><small class="text-muted">处理时长: ${task.processing_time.toFixed(2)}秒</small></div>` : ''}
                        ${task.output_length ? `<div class="mt-1"><small class="text-muted">输出字数: ${task.output_length}</small></div>` : ''}
                        ${task.text_model ? `<div class="mt-1"><small class="text-muted">文本模型: ${task.text_model}</small></div>` : ''}
                        ${task.image_model ? `<div class="mt-1"><small class="text-muted">图像模型: ${task.image_model}</small></div>` : ''}
                    </div>
                `;
            }
            activeTasksList.innerHTML = activeHtml;
        }
        
        // 渲染已完成任务
        if (Object.keys(completedTasks).length === 0) {
            completedTasksList.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="fas fa-inbox fa-2x mb-2"></i>
                    <p>暂无已完成的任务</p>
                </div>
            `;
        } else {
            let completedHtml = '';
            for (const taskId in completedTasks) {
                const task = completedTasks[taskId];
                completedHtml += `
                    <div class="task-item status-${task.status}">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="mb-1">
                                    ${(task.input_filenames && Array.isArray(task.input_filenames) && task.input_filenames.length > 1) 
                                        ? `批量处理: ${task.input_filenames.length} 个文件` 
                                        : (task.input_filenames && task.input_filenames.length === 1 ? task.input_filenames[0] : (task.input_filename || (taskId.substring(0, 8) + '...')))}
                                </h6>
                                <small class="text-muted">状态: ${getStatusText(task.status)}</small>
                            </div>
                            <div class="d-flex gap-2">
                                <span class="badge bg-secondary">${Math.round(task.progress || 0)}%</span>
                                <button class="btn btn-sm btn-danger" onclick="deleteTask('${taskId}')" title="删除任务">
                                    <i class="fas fa-trash-alt"></i>
                                </button>
                            </div>
                        </div>
                        
                        ${task.start_time ? `<div class="mt-1"><small class="text-muted">开始时间: ${new Date(task.start_time * 1000).toLocaleString()}</small></div>` : ''}
                        ${task.token_usage ? `<div class="mt-1"><small class="text-muted">Token用量: ${task.token_usage}</small></div>` : ''}
                        ${task.processing_time ? `<div class="mt-1"><small class="text-muted">处理时长: ${task.processing_time.toFixed(2)}秒</small></div>` : ''}
                        ${task.output_length ? `<div class="mt-1"><small class="text-muted">输出字数: ${task.output_length}</small></div>` : ''}
                        ${task.text_model ? `<div class="mt-1"><small class="text-muted">文本模型: ${task.text_model}</small></div>` : ''}
                        ${task.image_model ? `<div class="mt-1"><small class="text-muted">图像模型: ${task.image_model}</small></div>` : ''}
                        
                        ${task.status === 'failed' && task.error ? `
                        <div class="mt-2">
                            <button class="btn btn-sm btn-outline-danger" type="button" data-bs-toggle="collapse" data-bs-target="#error-${taskId}" aria-expanded="false">
                                查看错误详情
                            </button>
                            <div class="collapse" id="error-${taskId}">
                                <div class="card card-body mt-2 p-2">
                                    <pre class="mb-0" style="font-size: 0.8em; max-height: 150px; overflow-y: auto;">${task.error}</pre>
                                </div>
                            </div>
                        </div>
                        ` : ''}                     
                    </div>
                `;
            }
            completedTasksList.innerHTML = completedHtml;
        }
    })
    .catch(error => {
        console.error('Error loading tasks:', error);
        // 再次检查元素是否存在后再设置内容
        if (activeTasksList) {
            activeTasksList.innerHTML = `
                <div class="alert alert-danger">
                    加载任务列表失败: ${error.message}
                </div>
            `;
        }
        if (completedTasksList) {
            completedTasksList.innerHTML = '';
        }
    });
}

// 删除任务函数
window.deleteTask = function(taskId) {
    if (confirm('确定要删除此任务记录吗？此操作不可恢复。')) {
        fetch(`/delete_task/${taskId}`, {
            method: 'DELETE'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('删除失败');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showToast('任务删除成功', 'success');
                loadTasks(); // 重新加载任务列表
            } else {
                throw new Error(data.error || '删除失败');
            }
        })
        .catch(error => {
            console.error('删除任务失败:', error);
            showToast('删除失败: ' + error.message, 'error');
        });
    }
};

// 初始化任务管理功能
function initTaskManager() {
    // 保存原始的loadTasks函数（如果存在）
    if (window.loadTasks && typeof window.loadTasks === 'function' && !window.originalLoadTasks) {
        window.originalLoadTasks = window.loadTasks;
    }
    
    // 重命名我们的loadTasks函数以避免命名冲突
    const ourLoadTasks = loadTasks;
    
    // 覆盖全局loadTasks函数，但避免递归调用
    window.loadTasks = function() {
        ourLoadTasks();
    };
    
    // 添加全局getStatusText函数
    window.getStatusText = getStatusText;
    
    // 确保即使index.html中的loadTasks先执行也能正常工作
    // 当DOM完全加载后，我们的版本会覆盖原始实现
    
    // 确保在DOM加载完成后执行
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            initializeTaskManager();
        });
    } else {
        initializeTaskManager();
    }
}

// 内部初始化函数
function initializeTaskManager() {
    // 绑定刷新按钮事件
    if (document.getElementById('refreshTasks')) {
        document.getElementById('refreshTasks').addEventListener('click', loadTasks);
    }
    
    // 初始加载任务
    if (document.getElementById('activeTasksList') && document.getElementById('completedTasksList')) {
        loadTasks();
    }
}

// 立即执行初始化
initTaskManager();