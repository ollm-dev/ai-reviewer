import os
import datetime
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import concurrent.futures
import json

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

# 全局线程池执行器
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=5)


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
                prompt = get_markdown_prompt()

                # 创建任务完成标志
                tasks_complete = {"reasoning": False, "content": False, "json": False}
                # 创建异步事件以通知队列处理完成
                processing_complete = asyncio.Event()

                # 定义用于从队列获取数据并流式返回的协程
                async def stream_results():
                    while not (tasks_complete["reasoning"] and tasks_complete["content"] and tasks_complete["json"]):
                        try:
                            # 尝试从队列获取数据，设置超时以避免阻塞
                            try:
                                item = await asyncio.wait_for(result_queue.get(), timeout=0.1)
                                yield item
                            except asyncio.TimeoutError:
                                # 超时继续等待
                                pass
                        except Exception as e:
                            print(f"[ERROR] 队列读取异常: {str(e)}")
                    
                    # 处理队列中剩余的数据
                    while not result_queue.empty():
                        try:
                            item = result_queue.get_nowait()
                            yield item
                        except asyncio.QueueEmpty:
                            break

                # 定义在线程中执行的函数
                def run_reasoning_task():
                    # 执行推理任务并将结果放入队列
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        async def _process():
                            try:
                                # 调用处理函数并传递共享队列
                                await process_reasoning_task(all_text, result_queue, prompt)
                            except Exception as e:
                                print(f"[ERROR] 推理任务异常: {str(e)}")
                                error_msg = {
                                    "type": "error",
                                    "message": f"推理任务异常: {str(e)}"
                                }
                                await result_queue.put(f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n")
                            finally:
                                # 标记任务完成
                                tasks_complete["reasoning"] = True
                                
                        return loop.run_until_complete(_process())
                    finally:
                        loop.close()
                
                def run_content_task():
                    # 执行内容任务并将结果放入队列
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        async def _process():
                            try:
                                # 调用处理函数并传递共享队列
                                await process_content_task(all_text, result_queue, prompt)
                            except Exception as e:
                                print(f"[ERROR] 内容任务异常: {str(e)}")
                                error_msg = {
                                    "type": "error",
                                    "message": f"内容任务异常: {str(e)}"
                                }
                                await result_queue.put(f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n")
                            finally:
                                # 标记任务完成
                                tasks_complete["content"] = True
                                
                        return loop.run_until_complete(_process())
                    finally:
                        loop.close()
                
                def run_json_task():
                    # 执行JSON结构化任务并将结果放入队列
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        async def _process():
                            try:
                                # 调用处理函数并传递共享队列
                                await process_json_task(all_text, result_queue)
                            except Exception as e:
                                print(f"[ERROR] JSON任务异常: {str(e)}")
                                error_msg = {
                                    "type": "error",
                                    "message": f"JSON任务异常: {str(e)}"
                                }
                                await result_queue.put(f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n")
                            finally:
                                # 标记任务完成
                                tasks_complete["json"] = True
                                
                        return loop.run_until_complete(_process())
                    finally:
                        loop.close()
                
                # 提交任务到线程池
                reasoning_future = thread_pool.submit(run_reasoning_task)
                content_future = thread_pool.submit(run_content_task)
                json_future = thread_pool.submit(run_json_task)
                
                # 开始实时处理结果流
                async for result in stream_results():
                    yield result
                
                # 发送完成消息
                complete_msg = {
                    "type": "complete",
                    "message": "评审完成"
                }
                yield f"data: {json.dumps(complete_msg, ensure_ascii=False)}\n\n"
                
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
            'X-Accel-Buffering': 'no',  # 禁用Nginx缓冲，提高流式响应性能
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

# 应用关闭时关闭线程池
@app.on_event("shutdown")
async def shutdown_event():
    print("[INFO] 关闭线程池...")
    thread_pool.shutdown(wait=False)
    print("[INFO] 线程池已关闭")

if __name__ == "__main__":
     launch_app()