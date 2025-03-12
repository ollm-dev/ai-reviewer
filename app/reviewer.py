import gradio as gr
import tempfile
import os
from typing import Generator, Tuple, Any

from util.conf import get_conf
from util.review_paper import review_paper
from util.log import get_logger

conf = get_conf()

# 获取日志记录器
logger = get_logger("app.reviewer")

def review_tab():
    """论文评审页面"""
    
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
        
        /* 评审结果样式 */
        .review-result {
            font-size: 0.95rem;
            line-height: 1.6;
            color: #212121;
            padding: 0.5rem;
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

        def stream_handler(content: str) -> Generator[Tuple[str, str, str], Any, None]:
            """处理流式输出"""
            if "THOUGHT:" in content:
                # AI思考过程
                thought = content.split("THOUGHT:")[1].split("REVIEW JSON:")[0].strip()
                yield (
                    f"### 思考过程\n{thought}\n\n",
                    "AI 正在思考...",
                    ""
                )
            elif "反思过程:" in content:
                # 反思内容
                reflection = content.split("反思过程:")[1].strip()
                yield (
                    f"### 反思\n{reflection}\n\n",
                    "AI 正在反思...",
                    ""
                )
            elif "评审者" in content and "思考过程" in content:
                # 多评审者的思考
                reviewer = content.split("评审者")[1].split("的思考过程:")[0].strip()
                thought = content.split("的思考过程:")[1].strip()
                yield (
                    f"### 评审者 {reviewer}\n{thought}\n\n",
                    f"评审者 {reviewer} 正在评审...",
                    ""
                )
            elif "```json" in content:
                # JSON结果暂存不显示
                yield "", "正在整理评审报告...", ""
            else:
                # 其他进度信息
                yield "", content, ""

        def review_wrapper(file):
            if file is None:
                return "请先上传PDF文件", "请先上传PDF文件", ""
            progress_updates = []
            stream_contents = []

            def update_progress(msg):
                if msg not in progress_updates:
                    progress_updates.append(msg)
                    # 对不同类型的消息进行处理
                    for stream_content, progress, _ in stream_handler(msg):
                        if stream_content:
                            stream_contents.append(stream_content)
                        yield (
                            "\n".join(stream_contents), # 流式输出
                            progress if progress else "\n".join(progress_updates), # 进度更新
                            "" # 评审结果先置空
                        )
            
            try:
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                    temp_pdf.write(file)
                    temp_path = temp_pdf.name
                
                for progress in review_paper(temp_path, progress_callback=update_progress):
                    if isinstance(progress, tuple):
                        result, stats = progress
                        # 格式化最终结果
                        review_text = format_review_result(result, stats)
                        yield (
                            "\n".join(stream_contents),
                            "✅ 评审完成!",
                            review_text
                        )
                    
            except Exception as e:
                error_msg = f"❌ 评审过程出错: {str(e)}"
                logger.error(error_msg)  # 记录错误日志
                yield "", error_msg, "评审失败"
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        def format_review_result(result, stats):
            """格式化评审结果"""
            return f"""
            ## 📊 论文评审报告
            
            ### 📈 总体评价
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
            return "\n".join(f"- {item}" for item in items)

        review_button.click(
            fn=review_wrapper,
            inputs=[pdf_input],
            outputs=[stream_output, progress_output, review_output],
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