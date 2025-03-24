import os
import datetime
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 导入其他模块
from app.service.extractors import extract_pdf_text
from app.service.processors import process_task, process_json_task, process_reasoning_task, process_content_task

# 创建 FastAPI 应用
app = FastAPI(title="论文评审 API", description="提供论文评审服务的 API 接口")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)



class ReviewRequest(BaseModel):
    file_path: str
    num_reviewers: int = 1
    page_limit: int = 0
    use_claude: bool = False

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    上传 PDF 文件接口
    
    Args:
        file: PDF 文件
    
    Returns:
        Dict: 包含上传文件信息的字典
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="只接受 PDF 文件")
    
    try:
        # 创建临时文件
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_path = os.path.join(temp_dir, f"temp_{timestamp}_{file.filename}")
        
        # 添加日志
        print(f"[DEBUG] 临时目录: {temp_dir}")
        print(f"[DEBUG] 创建临时文件: {temp_path}")
        
        # 保存上传的文件
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # 验证文件创建
        if os.path.exists(temp_path):
            print(f"[DEBUG] 临时文件创建成功: {temp_path}")
            print(f"[DEBUG] 临时文件大小: {os.path.getsize(temp_path)} 字节")
        else:
            print(f"[ERROR] 临时文件创建失败: {temp_path}")
        
        return {
            "status": "success",
            "message": "文件上传成功",
            "file_path": temp_path,
            "file_name": file.filename
        }
    except Exception as e:
        print(f"[ERROR] 文件上传异常: {str(e)}")
        import traceback
        print(f"[ERROR] 异常堆栈: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

@app.post("/review")
async def review_paper_endpoint(request: ReviewRequest):
    """
    执行论文评审接口（流式响应）
                
    Args:
        request: ReviewRequest 对象，包含文件路径和评审参数
    
    Returns:
        StreamingResponse: 流式响应评审结果
    """
    from utils.get_prompt import get_markdown_prompt
    import asyncio
    import json

    # 检查文件路径
    print(f"[DEBUG] 尝试访问文件: {request.file_path}")
    if not os.path.exists(request.file_path):
        print(f"[ERROR] 文件不存在: {request.file_path}")
        raise HTTPException(status_code=404, detail="文件不存在")
    else:
        print(f"[DEBUG] 文件存在且可访问: {request.file_path}")
        print(f"[DEBUG] 文件大小: {os.path.getsize(request.file_path)} 字节")

    async def stream_generator():
        try:
            # 获取PDF文件名
            pdf_name = os.path.basename(request.file_path)
            print(f"[DEBUG] 开始处理PDF: {pdf_name}")
            
            try:
                # 第一阶段：提取PDF文本，直接流式返回进度
                text_gen = extract_pdf_text(request.file_path, request.page_limit)
                # 迭代所有消息
                all_text = ""
                async for message in text_gen:
                    # 检查是否是文本内容消息
                    if message.startswith('data:'):
                        # 直接传递进度消息给前端
                        yield message
                    else:
                        # 解析JSON获取文本内容或错误
                        result = json.loads(message)
                        if result["type"] == "extracted_text":
                            all_text = result["text"]
                        elif result["type"] == "error":
                            # 如果是错误，转换为SSE格式并传递给前端
                            error_msg = {
                                "type": "error",
                                "message": result["message"]
                            }
                            yield f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n"
                            return
                
                if not all_text or not all_text.strip():
                    raise Exception("PDF内容提取为空")
                
                print(f"[DEBUG] PDF文本提取完成，长度: {len(all_text)}")
                
                # 创建处理队列和任务
                result_queue = asyncio.Queue()
                
                # 创建任务组
                tasks = []
                
                # 添加推理任务
                tasks.append(asyncio.create_task(process_reasoning_task(
                    all_text, result_queue, get_markdown_prompt()
                )))
                
                # 添加内容任务
                tasks.append(asyncio.create_task(process_content_task(
                    all_text, result_queue, get_markdown_prompt()
                )))
                
                # 添加JSON结构化任务
                tasks.append(asyncio.create_task(process_json_task(
                    all_text, result_queue
                )))
                
                # 持续从队列获取结果并传递给客户端
                while tasks or not result_queue.empty():
                    # 检查是否有已完成的任务
                    done_tasks = []
                    for task in tasks:
                        if task.done():
                            done_tasks.append(task)
                    
                    # 从任务列表中移除已完成的任务
                    for task in done_tasks:
                        tasks.remove(task)
                    
                    # 如果队列中有结果，立即返回
                    if not result_queue.empty():
                        message = await result_queue.get()
                        yield message
                    # 如果队列为空但任务仍在进行，等待短暂时间
                    elif tasks:
                        await asyncio.sleep(0.01)  # 减少等待时间，增加响应速度
                
            except Exception as e:
                print(f"[ERROR] 处理异常: {str(e)}")
                import traceback
                print(f"[ERROR] 处理异常堆栈: {traceback.format_exc()}")
                error_msg = {
                    "type": "error",
                    "message": str(e)
                }
                yield f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n"
                
        except Exception as e:
            print(f"[ERROR] 流处理异常: {str(e)}")
            import traceback
            print(f"[ERROR] 流处理异常堆栈: {traceback.format_exc()}")
            error_msg = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n"
        finally:
            # 清理临时文件
            try:
                if os.path.exists(request.file_path):
                    print(f"[DEBUG] 清理临时文件: {request.file_path}")
                    os.unlink(request.file_path)
                    print(f"[DEBUG] 临时文件已清理")
                else:
                    print(f"[DEBUG] 临时文件不存在，无需清理: {request.file_path}")
            except Exception as clean_err:
                print(f"[ERROR] 临时文件清理失败: {str(clean_err)}")

    return StreamingResponse(
        stream_generator(),
        media_type='text/event-stream',
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        }
    )

def launch_app(host="localhost", port=5555):
    """
    启动论文评审API服务
    
    Args:
        host: 主机地址，默认为127.0.0.1
        port: 端口号，默认为5555
    """
    import uvicorn
    uvicorn.run(app, host=host, port=port) 
if __name__ == "__main__":
     launch_app()