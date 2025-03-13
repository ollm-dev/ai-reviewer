import gradio as gr
import tempfile
import os
import time
from typing import Generator, Tuple, Any, List, Dict
from datetime import datetime

from util.conf import get_conf
from util.review_paper import review_paper
from util.log import get_logger

conf = get_conf()

# 获取日志记录器
logger = get_logger("app.reviewer")

def review_tab():
    """论文评审页面
    
    Returns:
        gr.Tab: Gradio标签页组件
    """
    
    with gr.Tab("论文评审"):
        # 自定义CSS
        gr.HTML("""
        <style>
        /* 全局样式 */
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 1rem;
        }
        
        /* 标题样式 */
        .header {
            text-align: center;
            margin: 0.5rem 0 1.5rem;
            padding: 1.5rem;
            background: linear-gradient(135deg, #1a237e 0%, #0d47a1 100%);
            color: white;
            border-radius: 8px;
        }
        
        .header h1 {
            font-size: 2rem;
            margin-bottom: 0.5rem;
            font-weight: 500;
        }
        
        .header p {
            font-size: 1rem;
            opacity: 0.9;
        }
        
        /* 面板样式 */
        .panel {
            background: white;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
            border: 1px solid #e0e0e0;
        }
        
        /* 上传区域样式 */
        .upload-area {
            text-align: center;
            padding: 1.5rem;
            border: 2px dashed #bbdefb;
            border-radius: 8px;
            background: #f8f9fa;
            transition: all 0.3s ease;
            margin: 0.5rem 0;
        }
        
        .upload-area:hover {
            border-color: #2196f3;
            background: #e3f2fd;
        }
        
        /* 按钮样式 */
        .custom-button {
            background: #1976d2;
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            border: none;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .custom-button:hover {
            background: #1565c0;
        }
        
        /* 进度区域样式 */
        .progress-info {
            padding: 0.75rem;
            background: #f5f5f5;
            border-radius: 4px;
            border-left: 3px solid #2196f3;
            font-size: 0.9rem;
            line-height: 1.4;
            color: #424242;
            margin: 0.5rem 0;
        }
        
        /* 输出区域样式 */
        .stream-output {
            font-family: "SF Mono", "Consolas", monospace;
            font-size: 0.9rem;
            line-height: 1.5;
            padding: 1rem;
            background: #1e1e1e;
            color: #e0e0e0;
            border-radius: 6px;
            height: 400px;
            overflow-y: auto;
            white-space: pre-wrap;
            margin: 0.5rem 0;
        }
        
        .stream-output::-webkit-scrollbar {
            width: 6px;
        }
        
        .stream-output::-webkit-scrollbar-track {
            background: #2d2d2d;
        }
        
        .stream-output::-webkit-scrollbar-thumb {
            background: #666;
            border-radius: 3px;
        }
        
        /* 日志样式 */
        .stream-output h3 {
            color: #4fc3f7;
            margin: 1rem 0 0.5rem;
            font-size: 1.1rem;
            font-weight: 600;
            border-bottom: 1px solid #444;
            padding-bottom: 0.3rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .stream-output pre, .stream-output code {
            background: #2d2d2d;
            padding: 0.8rem;
            border-radius: 4px;
            font-size: 0.9rem;
            overflow-x: auto;
            margin: 0.5rem 0;
            border: 1px solid #444;
            line-height: 1.5;
        }
        
        /* 特殊日志类型样式 */
        .stream-output h3:nth-of-type(1) {
            margin-top: 0;
        }
        
        /* 文件处理样式 */
        .stream-output h3:contains("文件加载"),
        .stream-output h3:contains("PDF处理") {
            color: #64b5f6;
        }
        
        /* 思考过程样式 */
        .stream-output h3:contains("思考过程") {
            color: #81c784;
        }
        
        /* 评审者样式 */
        .stream-output h3:contains("评审者") {
            color: #9575cd;
        }
        
        /* 反思过程样式 */
        .stream-output h3:contains("反思") {
            color: #ffb74d;
        }
        
        /* 完成样式 */
        .stream-output h3:contains("完成") {
            color: #4caf50;
        }
        
        /* 错误样式 */
        .stream-output h3:contains("错误") {
            color: #e57373;
        }
        
        /* Token统计样式 */
        .stream-output h3:contains("Token统计") {
            color: #7986cb;
        }
        
        /* 进度样式 */
        .stream-output h3:contains("进度") {
            color: #90a4ae;
        }
        
        /* 代码块样式优化 */
        .stream-output pre {
            position: relative;
            padding-top: 2.5rem;
            margin: 1rem 0;
            background: #1e1e1e;
            border: 1px solid #444;
        }
        
        .stream-output pre::before {
            content: attr(data-type);
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            padding: 0.5rem 1rem;
            background: #333;
            color: #e0e0e0;
            font-size: 0.9rem;
            border-bottom: 1px solid #444;
        }
        
        /* 自动滚动动画优化 */
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .stream-output > div {
            animation: fadeInUp 0.3s ease-out forwards;
        }
        
        /* 评审结果样式 */
        .review-result {
            background: #1e1e1e;
            border-left: 3px solid #64b5f6;
            padding: 1rem;
            margin: 0.5rem 0;
            border-radius: 0 4px 4px 0;
        }
        
        .review-result h2 {
            color: #1976d2;
            font-size: 1.4rem;
            font-weight: 500;
            margin: 1rem 0 0.75rem;
            padding-bottom: 0.4rem;
            border-bottom: 2px solid #e3f2fd;
        }
        
        .review-result h3 {
            color: #2196f3;
            font-size: 1.1rem;
            font-weight: 500;
            margin: 1rem 0 0.5rem;
        }
        
        .review-result ul {
            margin: 0.4rem 0;
            padding-left: 1.2rem;
        }
        
        .review-result li {
            margin: 0.4rem 0;
            color: #424242;
        }
        
        /* 统计信息样式 */
        .stats-info {
            margin: 1rem 0;
            padding: 0.75rem;
            background: #e3f2fd;
            border-radius: 6px;
            font-size: 0.85rem;
            color: #1976d2;
        }

        /* 分栏间距 */
        .gap-right {
            margin-right: 1rem;
        }
        
        /* 标题样式 */
        .section-title {
            font-size: 1rem;
            color: #424242;
            margin: 0.5rem 0;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        /* 图标样式 */
        .icon {
            opacity: 0.8;
        }
        
        /* 自动滚动到底部 */
        .auto-scroll {
            animation: scroll-to-bottom 0.5s ease;
        }
        
        @keyframes scroll-to-bottom {
            from {
                transform: translateY(0);
            }
            to {
                transform: translateY(100%);
            }
        }
        
        /* 评审过程容器 */
        .review-process {
            border: 1px solid #444;
            border-radius: 8px;
            margin: 1rem 0;
            background: #2d2d2d;
        }
        
        .review-process-header {
            background: #444;
            padding: 0.5rem 1rem;
            border-radius: 8px 8px 0 0;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: #fff;
        }
        
        .review-process-content {
            padding: 1rem;
        }
        
        /* 评审者思考样式 */
        .reviewer-thought {
            background: #1e1e1e;
            border-left: 3px solid #81c784;
            padding: 1rem;
            margin: 0.5rem 0;
            border-radius: 0 4px 4px 0;
        }
        
        /* 反思过程样式 */
        .reflection-process {
            background: #1e1e1e;
            border-left: 3px solid #ffb74d;
            padding: 1rem;
            margin: 0.5rem 0;
            border-radius: 0 4px 4px 0;
        }
        
        /* 评审者标签样式 */
        .reviewer-tag {
            display: inline-block;
            padding: 0.2rem 0.5rem;
            background: #1e88e5;
            color: white;
            border-radius: 4px;
            font-size: 0.8rem;
            margin-right: 0.5rem;
        }
        
        /* 反思轮次标签样式 */
        .reflection-round {
            display: inline-block;
            padding: 0.2rem 0.5rem;
            background: #fb8c00;
            color: white;
            border-radius: 4px;
            font-size: 0.8rem;
            margin-right: 0.5rem;
        }
        
        /* 日志面板样式 */
        .log-panel {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 4px;
            margin: 1rem 0;
            font-family: 'Consolas', 'Monaco', monospace;
        }
        
        .log-panel-header {
            background: #333;
            color: #fff;
            padding: 0.5rem 1rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid #444;
        }
        
        .log-panel-content {
            padding: 0.5rem;
            max-height: 200px;
            overflow-y: auto;
        }
        
        .log-entry {
            padding: 0.25rem 0.5rem;
            border-radius: 2px;
            margin: 2px 0;
            font-size: 0.9rem;
            font-family: monospace;
            white-space: pre-wrap;
            word-break: break-all;
        }
        
        .log-debug {
            color: #8bc34a;
            background: rgba(139, 195, 74, 0.1);
        }
        
        .log-info {
            color: #03a9f4;
            background: rgba(3, 169, 244, 0.1);
        }
        
        .log-warning {
            color: #ffc107;
            background: rgba(255, 193, 7, 0.1);
        }
        
        .log-error {
            color: #f44336;
            background: rgba(244, 67, 54, 0.1);
        }
        
        .timestamp {
            color: #666;
            font-size: 0.8rem;
            margin-right: 0.5rem;
        }
        </style>
        
        <div class="header">
            <h1>论文智能评审系统</h1>
            <p>AI Reviewer，帮助您快速分析论文优劣</p>
        </div>
        """)
        
        with gr.Row(equal_height=True):
            # 左侧面板
            with gr.Column(scale=1, elem_classes=["gap-right"]):
                with gr.Group(elem_classes=["panel"]):
                    gr.Markdown(
                        "### 📄 上传论文",
                        elem_classes=["section-title"]
                    )
                    with gr.Group(elem_classes=["upload-area"]):
                        pdf_input = gr.File(
                            label="支持 PDF 格式",
                            file_types=[".pdf"],
                            type="binary"
                        )
                        review_button = gr.Button(
                            "开始评审",
                            variant="primary",
                            elem_classes=["custom-button"]
                        )
                
                with gr.Group(elem_classes=["panel"]):
                    gr.Markdown(
                        "### 📊 评审进度",
                        elem_classes=["section-title"]
                    )
                    progress_output = gr.Markdown(
                        "准备就绪...",
                        elem_classes=["progress-info"]
                    )
                    
                # 添加日志面板
                with gr.Group(elem_classes=["panel"]):
                    gr.Markdown(
                        "### 🔍 系统日志",
                        elem_classes=["section-title"]
                    )
                    log_output = gr.HTML(
                        """<div class="log-panel">
                            <div class="log-panel-header">
                                <span>实时日志</span>
                                <span class="log-count">0 条</span>
                            </div>
                            <div class="log-panel-content"></div>
                        </div>""",
                        elem_classes=["log-container"]
                    )

            # 右侧面板    
            with gr.Column(scale=2):
                with gr.Group(elem_classes=["panel"]):
                    gr.Markdown(
                        "### 🤖 AI 评审过程",
                        elem_classes=["section-title"]
                    )
                    stream_output = gr.Markdown(
                        elem_classes=["stream-output"]
                    )
                
                with gr.Group(elem_classes=["panel"]):
                    with gr.Row():
                        gr.Markdown(
                            "### 📝 评审结果",
                            elem_classes=["section-title"]
                        )
                        copy_button = gr.Button(
                            "📋 复制",
                            size="sm",
                            elem_classes=["custom-button"]
                        )
                    review_output = gr.Markdown(
                        elem_classes=["review-result"]
                    )

        def stream_handler(content: str) -> Generator[Tuple[str, str, str, str], Any, None]:
            """处理流式输出
            Returns:
                Generator[Tuple[str, str, str, str], Any, None]: 生成器返回四元组 (stream_content, progress_content, review_content, log_content)
            """
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # 处理日志信息
            if "[DEBUG]" in content:
                log_entry = f"""<div class="log-entry log-debug">
                    <span class="timestamp">{timestamp}</span>
                    {content}
                </div>"""
            elif "[INFO]" in content:
                log_entry = f"""<div class="log-entry log-info">
                    <span class="timestamp">{timestamp}</span>
                    {content}
                </div>"""
            elif "[WARNING]" in content:
                log_entry = f"""<div class="log-entry log-warning">
                    <span class="timestamp">{timestamp}</span>
                    {content}
                </div>"""
            elif "[ERROR]" in content:
                log_entry = f"""<div class="log-entry log-error">
                    <span class="timestamp">{timestamp}</span>
                    {content}
                </div>"""
            else:
                log_entry = None

            # 示例加载相关
            if "正在加载评审示例" in content:
                yield (
                    f"### 📚 示例加载\n{content}\n\n",
                    content,
                    "",
                    log_entry
                )
            elif "已加载" in content and "个评审示例" in content:
                yield (
                    f"### ✅ 示例准备完成\n{content}\n\n",
                    content,
                    "",
                    log_entry
                )
            # 评审提示相关
            elif "正在准备评审提示" in content:
                yield (
                    f"### 📝 评审准备\n{content}\n\n",
                    content,
                    "",
                    log_entry
                )
            elif "评审提示准备完成" in content:
                yield (
                    f"### ✅ 提示准备完成\n{content}\n\n",
                    content,
                    "",
                    log_entry
                )
            # 文件处理相关
            elif "开始加载文件:" in content:
                file_info = content.split("开始加载文件:")[1].strip()
                yield (
                    f"### 📂 文件加载\n正在加载文件: {file_info}\n\n",
                    "正在加载PDF文件...",
                    "",
                    log_entry
                )
            elif "使用 pymupdf4llm" in content:
                yield (
                    f"### 📄 PDF处理\n{content}\n\n",
                    "正在解析PDF内容...",
                    "",
                    log_entry
                )
            # 评审生成相关
            elif "开始生成" in content and "个评审意见" in content:
                yield (
                    f"### 🚀 开始评审\n{content}\n\n",
                    content,
                    "",
                    log_entry
                )
            elif "已生成" in content and "个评审意见" in content:
                yield (
                    f"### ✨ 评审生成完成\n{content}\n\n",
                    content,
                    "",
                    log_entry
                )
            # 评审者思考相关
            elif "评审者" in content and "的思考过程:" in content:
                reviewer_info = content.split("评审者")[1].split("的思考过程:")[0].strip()
                thought = content.split("的思考过程:")[1].strip()
                yield (
                    f"""<div class="review-process">
                        <div class="review-process-header">
                            <span class="reviewer-tag">评审者 {reviewer_info}</span>
                            <span>思考过程</span>
                        </div>
                        <div class="review-process-content">
                            <div class="reviewer-thought">
                                {thought}
                            </div>
                        </div>
                    </div>""",
                    f"评审者 {reviewer_info} 正在评审...",
                    "",
                    log_entry
                )
            # 评审解析相关
            elif "评审 " in content and " 解析成功" in content:
                yield (
                    f"### ✅ 解析成功\n{content}\n\n",
                    content,
                    "",
                    log_entry
                )
            elif "评审 " in content and " 解析失败" in content:
                error_info = content.strip()
                yield (
                    f"### ❌ 解析错误\n```错误\n{error_info}\n```\n\n",
                    "评审解析出现问题...",
                    "",
                    log_entry
                )
            elif "成功解析" in content and "个评审意见" in content:
                yield (
                    f"### ✅ 解析完成\n{content}\n\n",
                    content,
                    "",
                    log_entry
                )
            # 元评审相关
            elif "正在生成元评审" in content:
                yield (
                    f"### 🔄 元评审生成\n{content}\n\n",
                    content,
                    "",
                    log_entry
                )
            elif "元评审生成失败" in content:
                yield (
                    f"### ⚠️ 元评审失败\n{content}\n\n",
                    content,
                    "",
                    log_entry
                )
            elif "元评审生成成功" in content:
                yield (
                    f"### ✅ 元评审完成\n{content}\n\n",
                    content,
                    "",
                    log_entry
                )
            # 评分统计相关
            elif "正在计算评分统计" in content:
                yield (
                    f"### �� 评分计算\n{content}\n\n",
                    content,
                    "",
                    log_entry
                )
            elif "评分统计计算完成" in content:
                yield (
                    f"### ✅ 评分计算完成\n{content}\n\n",
                    content,
                    "",
                    log_entry
                )
            # 反思过程相关
            elif "反思过程:" in content:
                reflection = content.split("反思过程:")[1].strip()
                yield (
                    f"""<div class="review-process">
                        <div class="review-process-header">
                            <span>🔄 反思过程</span>
                        </div>
                        <div class="review-process-content">
                            <div class="reflection-process">
                                {reflection}
                            </div>
                        </div>
                    </div>""",
                    "AI 正在反思评审结果...",
                    "",
                    log_entry
                )
            elif "反思轮次:" in content:
                round_info = content.split("反思轮次:")[1].strip().split("\n")[0]
                yield (
                    f"""<div class="review-process">
                        <div class="review-process-header">
                            <span class="reflection-round">轮次 {round_info}</span>
                            <span>反思进行中</span>
                        </div>
                    </div>""",
                    f"进行{round_info}...",
                    "",
                    log_entry
                )
            elif "反思结果已更新" in content:
                yield (
                    f"""<div class="review-process">
                        <div class="review-process-header">
                            <span>✅ 反思结果更新</span>
                        </div>
                        <div class="review-process-content">
                            <div class="review-result">
                                反思产生了新的评审结果
                            </div>
                        </div>
                    </div>""",
                    content,
                    "",
                    log_entry
                )
            elif "反思未产生新的评审结果" in content:
                yield (
                    f"""<div class="review-process">
                        <div class="review-process-header">
                            <span>ℹ️ 反思结果</span>
                        </div>
                        <div class="review-process-content">
                            <div class="review-result">
                                当前评审结果无需更新
                            </div>
                        </div>
                    </div>""",
                    content,
                    "",
                    log_entry
                )
            elif "反思完成" in content:
                yield (
                    f"""<div class="review-process">
                        <div class="review-process-header">
                            <span>✅ 反思完成</span>
                        </div>
                        <div class="review-process-content">
                            <div class="review-result">
                                反思已完成，评审结果已优化
                            </div>
                        </div>
                    </div>""",
                    "反思评审已完成",
                    "",
                    log_entry
                )
            # 完成相关
            elif "评审完成" in content:
                yield (
                    f"### ✅ 评审完成\n\n",
                    "评审已完成，正在整理结果...",
                    "",
                    log_entry
                )
            elif "Token 使用统计:" in content:
                stats = content.split("Token 使用统计:")[1].strip()
                yield (
                    f"### 📊 Token统计\n```统计\n{stats}\n```\n\n",
                    "评审已完成",
                    "",
                    log_entry
                )
            # 错误相关
            elif "评审过程出错" in content:
                error_info = content.split("评审过程出错:")[1].strip()
                yield (
                    f"### ❌ 评审错误\n```错误\n{error_info}\n```\n\n",
                    "评审过程出现错误",
                    "",
                    log_entry
                )
            elif "```json" in content:
                yield (
                    "",
                    "正在整理评审报告...",
                    "",
                    log_entry
                )
            else:
                yield (
                    f"### ℹ️ 进度\n{content}\n\n",
                    content,
                    "",
                    log_entry
                )

        def review_wrapper(file):
            """评审包装函数
            
            Args:
                file: PDF文件
                
            Returns:
                Generator: 生成UI更新的生成器
            """
            if file is None:
                return "请先上传PDF文件", "请先上传PDF文件", "", ""
            
            progress_updates = []
            stream_contents = []
            log_contents = []

            def update_progress(msg):
                if msg not in progress_updates:
                    progress_updates.append(msg)
                    for stream_content, progress, review, log in stream_handler(msg):
                        if stream_content:
                            stream_contents.append(stream_content)
                        if log:
                            log_contents.append(log)
                        # 更新日志面板的内容
                        log_panel = f"""<div class="log-panel">
                            <div class="log-panel-header">
                                <span>实时日志</span>
                                <span class="log-count">{len(log_contents)} 条</span>
                            </div>
                            <div class="log-panel-content">
                                {''.join(log_contents)}
                            </div>
                        </div>"""
                        yield (
                            "\n".join(stream_contents),
                            progress if progress else "\n".join(progress_updates[-3:]),
                            review,
                            log_panel
                        )
            
            try:
                logger.info("开始处理上传的PDF文件")
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                    temp_pdf.write(file)
                    temp_path = temp_pdf.name
                
                for initial_update in [
                    "1. 任务初始化完成",
                    "2. 正在准备模型..."
                ]:
                    for content in update_progress(initial_update):
                        yield content
                
                for progress in review_paper(temp_path, progress_callback=update_progress):
                    # 如果是最终结果
                    if isinstance(progress, tuple) and len(progress) == 2:
                        result, stats = progress
                        review_text = format_review_result(result, stats)
                        # 更新日志面板
                        log_panel = f"""<div class="log-panel">
                            <div class="log-panel-header">
                                <span>实时日志</span>
                                <span class="log-count">{len(log_contents)} 条</span>
                            </div>
                            <div class="log-panel-content">
                                {''.join(log_contents)}
                            </div>
                        </div>"""
                        yield (
                            "\n".join(stream_contents),
                            "✅ 评审完成!",
                            review_text,
                            log_panel
                        )
                    
            except Exception as e:
                error_msg = f"❌ 评审过程出错: {str(e)}"
                logger.error(error_msg)
                # 添加错误日志
                timestamp = datetime.now().strftime("%H:%M:%S")
                log_contents.append(f"""<div class="log-entry log-error">
                    <span class="timestamp">{timestamp}</span>
                    {error_msg}
                </div>""")
                log_panel = f"""<div class="log-panel">
                    <div class="log-panel-header">
                        <span>实时日志</span>
                        <span class="log-count">{len(log_contents)} 条</span>
                    </div>
                    <div class="log-panel-content">
                        {''.join(log_contents)}
                    </div>
                </div>"""
                yield (
                    "\n".join(stream_contents) + f"\n\n### ❌ 错误\n```\n{str(e)}\n```",
                    error_msg,
                    "评审失败",
                    log_panel
                )
            finally:
                if 'temp_path' in locals() and os.path.exists(temp_path):
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.unlink(temp_path)

        def format_review_result(result, stats):
            """格式化评审结果
            
            Args:
                result: 评审结果
                stats: 统计信息
                
            Returns:
                str: 格式化后的评审结果
            """
            return f"""
            ## 📊 论文评审报告
            
            ### 📊 总体评价
            - 评分: {result.get('Overall', 'N/A')}/10
            - 决定: {result.get('Decision', 'N/A')}
            
            ### ✨ 主要优点
            {format_list(result.get('Strengths', []))}
            
            ### ❗ 存在问题
            {format_list(result.get('Weaknesses', []))}
            
            ### 💡 建议改进
            {format_list(result.get('Questions', []))}
            
            <div class="stats-info">
            ### 📊 评审统计
            - 总计 tokens: {stats.get('total_tokens', 0):,}
            - 预估费用: ¥{stats.get('total_cost', 0):.4f}
            </div>
            """

        def format_list(items):
            """格式化列表
            
            Args:
                items: 列表项
                
            Returns:
                str: 格式化后的列表
            """
            return "\n".join(f"- {item}" for item in items)

        # 绑定评审按钮点击事件
        review_button.click(
            fn=review_wrapper,
            inputs=[pdf_input],
            outputs=[stream_output, progress_output, review_output, log_output],
            show_progress=True
        )

        # 复制功能
        copy_js = """
            (output) => {
                if (!output) return;
                navigator.clipboard.writeText(output);
                const notify = window.notifyOnSuccess || window.notify;
                if (notify) notify({ msg: "已复制到剪贴板!", type: "success" });
            }
        """
        copy_button.click(
            fn=None,
            inputs=[review_output],
            outputs=None,
            js=copy_js
        )
        
        # 自动滚动功能
        auto_scroll_js = """
            () => {
                // 找到所有stream-output类的元素
                const outputElements = document.getElementsByClassName('stream-output');
                if (outputElements.length > 0) {
                    // 对每个元素设置滚动到底部
                    Array.from(outputElements).forEach(el => {
                        el.scrollTop = el.scrollHeight;
                    });
                }
                return null;
            }
        """
        
        # 每秒自动滚动一次
        gr.HTML("""
        <script>
            // 设置自动滚动定时器
            document.addEventListener('DOMContentLoaded', function() {
                setInterval(function() {
                    const outputElements = document.getElementsByClassName('stream-output');
                    if (outputElements.length > 0) {
                        Array.from(outputElements).forEach(el => {
                            el.scrollTop = el.scrollHeight;
                        });
                    }
                }, 1000);
            });
        </script>
        """)   