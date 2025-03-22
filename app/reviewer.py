import tempfile
import os
import datetime
import pathlib
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import PyPDF2
import json
import queue
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
# 导入评审函数
from util.review_paper import review_paper
from util.conf import get_conf

# 获取配置
conf = get_conf()

# 使用 OpenAI 客户端
import openai

# 创建 OpenAI 客户端
client = openai.OpenAI(
  api_key=conf["model"]["api_key"],
  base_url=conf["model"]["api_base"]
)

app = FastAPI(title="论文评审 API", description="提供论文评审服务的 API 接口")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)

# 创建结果目录
results_dir = pathlib.Path("results")
results_dir.mkdir(exist_ok=True)

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

# 添加读取 JSON 提示词的函数
def get_json_prompt():
    """读取 JSON 格式化提示词"""
    try:
        prompt_path = os.path.join("doc", "Josn_prompt.md")
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"[ERROR] 读取 JSON 提示词失败: {str(e)}")
        return ""  # 如果读取失败，返回空字符串，不影响原有功能

# 添加从论文内容提取JSON结构的函数
async def extract_json_structure(paper_text, json_queue):
    """
    从论文内容中提取JSON结构
    
    Args:
        paper_text: 论文文本内容
        json_queue: 用于传递JSON结果的队列
    """
    try:
        # 获取JSON提示词
        json_prompt = get_json_prompt()
        if not json_prompt:
            print("[WARNING] 没有找到JSON提示词，无法生成结构化数据")
            error_msg = {
                "type": "error",
                "message": "没有找到JSON提示词，无法生成结构化数据"
            }
            await json_queue.put(f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n")
            return
        
        # 调用模型生成JSON结构
        print("[DEBUG] 开始生成JSON结构化数据")
        response = client.chat.completions.create(
            model="deepseek-r1-250120",  # 使用与评审相同的模型
            messages=[
                {"role": "system", "content": json_prompt},
                {"role": "user", "content": f"请从以下论文中提取json结构化信息:\n\n{paper_text}"}  # 限制文本长度
            ],
            temperature=0.1,  # 低温度以获得一致的结果
            stream=True
        )
        full_content = ""  # 用于收集完整JSON结构给前端渲染
        for chunk in response:
            if hasattr(chunk.choices[0].delta, 'content'):
                content = chunk.choices[0].delta.content
                full_content += content
                json_result = {
                    "type": "json_structure",
                    "json_structure": content
                }
                await json_queue.put(f"data: {json.dumps(json_result, ensure_ascii=False)}\n\n")
                await asyncio.sleep(0.001)
        
        # 输出完整JSON结构
        full_json_result = {
            "type": "json_complete",
            "json_structure": full_content
        }
        await json_queue.put(f"data: {json.dumps(full_json_result, ensure_ascii=False)}\n\n")
        print(f"[DEBUG] JSON结构生成完成")
        
    except Exception as e:
        print(f"[ERROR] 生成JSON结构异常: {str(e)}")
        import traceback
        print(f"[ERROR] JSON结构生成异常堆栈: {traceback.format_exc()}")
        error_msg = {
            "type": "error",
            "message": str(e)
        }
        await json_queue.put(f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n")

# 提取PDF文本的函数
async def extract_pdf_text(pdf_path, page_limit):
    """
    异步提取PDF文本内容
    
    Args:
        pdf_path: PDF文件路径
        page_limit: 页数限制，0表示不限制
        
    Yields:
        str: 进度消息或最终文本内容
    """
    all_text = ""
    
    try:
        print(f"[DEBUG] 开始读取PDF文件: {pdf_path}")
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            num_pages = len(reader.pages)
            print(f"[DEBUG] PDF读取成功，共 {num_pages} 页")
            
            # 确定要处理的页数
            pages_to_load = num_pages
            if page_limit > 0 and page_limit < num_pages:
                pages_to_load = page_limit
            
            # 提取文本
            for i in range(pages_to_load):
                print(f"[DEBUG] 正在提取第 {i+1}/{pages_to_load} 页")
                page = reader.pages[i]
                text = page.extract_text()
                all_text += text + "\n\n"
                
                # 生成进度信息
                progress = {
                    "type": "progress",
                    "current": i + 1,
                    "total": pages_to_load,
                    "message": f"正在处理第 {i + 1}/{pages_to_load} 页"
                }
                # 直接生成进度消息
                yield f"data: {json.dumps(progress, ensure_ascii=False)}\n\n"
                
                # 适当地让出控制权
                await asyncio.sleep(0.001)
            
            # 最后yield文本内容，而不是return
            text_result = {
                "type": "extracted_text",
                "text": all_text
            }
            yield json.dumps(text_result, ensure_ascii=False)
            
    except Exception as e:
        import traceback
        print(f"[ERROR] PDF提取异常: {str(e)}")
        print(f"[ERROR] PDF提取异常堆栈: {traceback.format_exc()}")
        error_result = {
            "type": "error",
            "message": str(e)
        }
        yield json.dumps(error_result, ensure_ascii=False)

# 处理推理过程的函数
async def process_reasoning(paper_text, reasoning_queue):
    """
    异步处理AI评审推理过程
    
    Args:
        paper_text: 论文文本内容
        reasoning_queue: 用于传递推理结果的队列
    """
    try:
        # 获取 Markdown 提示词
        markdown_prompt = get_markdown_prompt()

        # 构建系统提示词，添加 Markdown 格式要求
        system_prompt = "你是一个专业的论文评审专家，请专注于思考和推理过程，对以下论文进行评审："
        if markdown_prompt:
            system_prompt = f"你的角色是:\n\n{system_prompt},你的输出格式需要遵循以下要求：{markdown_prompt}"

        print(f"[DEBUG] 开始调用AI评审推理过程")
        
        # 创建一个特殊请求获取推理过程
        response = client.chat.completions.create(
            model="deepseek-r1-250120",
            messages=[
                {"role": "system", "content": system_prompt + paper_text},
            ],
            temperature=0.1,
            stream=True
        )
        
        for chunk in response:
            # 获取思考过程
            if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[0].delta.reasoning_content:
                reasoning_content = chunk.choices[0].delta.reasoning_content
                data = {
                    "type": "reasoning",
                    "reasoning": reasoning_content
                }
                await reasoning_queue.put(f"data: {json.dumps(data, ensure_ascii=False)}\n\n")
                
                # 定期让出控制权
                if len(reasoning_content) > 20:
                    await asyncio.sleep(0.001)
        
        # 发送完成信息
        complete_msg = {
            "type": "reasoning_complete",
            "message": "推理过程完成"
        }
        await reasoning_queue.put(f"data: {json.dumps(complete_msg, ensure_ascii=False)}\n\n")
        print(f"[DEBUG] AI推理过程完成")
        
    except Exception as e:
        import traceback
        print(f"[ERROR] AI推理过程异常: {str(e)}")
        print(f"[ERROR] AI推理过程异常堆栈: {traceback.format_exc()}")
        error_msg = {
            "type": "error",
            "message": str(e)
        }
        await reasoning_queue.put(f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n")

# 处理内容输出的函数
async def process_content(paper_text, content_queue):
    """
    异步处理AI评审内容输出
    
    Args:
        paper_text: 论文文本内容
        content_queue: 用于传递内容结果的队列
    """
    try:
        # 获取 Markdown 提示词
        markdown_prompt = get_markdown_prompt()

        # 构建系统提示词，添加 Markdown 格式要求
        system_prompt = "你是一个专业的论文评审专家，请专注于评审内容的输出，对以下论文进行评审："
        if markdown_prompt:
            system_prompt = f"你的角色是:\n\n{system_prompt},你的输出格式需要遵循以下要求：{markdown_prompt}"

        print(f"[DEBUG] 开始调用AI评审内容输出")
        
        # 创建一个专门获取内容的请求
        response = client.chat.completions.create(
            model="deepseek-r1-250120",
            messages=[
                {"role": "system", "content": system_prompt + paper_text},
            ],
            temperature=0.1,
            stream=True
        )
        
        for chunk in response:
            # 获取内容
            if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                data = {
                    "type": "content",
                    "content": content
                }
                await content_queue.put(f"data: {json.dumps(data, ensure_ascii=False)}\n\n")
                
                # 定期让出控制权
                if len(content) > 20:
                    await asyncio.sleep(0.001)
        
        # 发送完成信息
        complete_msg = {
            "type": "complete",
            "message": "评审完成"
        }
        await content_queue.put(f"data: {json.dumps(complete_msg, ensure_ascii=False)}\n\n")
        print(f"[DEBUG] AI内容输出完成")
        
    except Exception as e:
        import traceback
        print(f"[ERROR] AI内容输出异常: {str(e)}")
        print(f"[ERROR] AI内容输出异常堆栈: {traceback.format_exc()}")
        error_msg = {
            "type": "error",
            "message": str(e)
        }
        await content_queue.put(f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n")

@app.post("/review")
async def review_paper_endpoint(request: ReviewRequest):
    """
    执行论文评审接口（流式响应）
                
    Args:
        request: ReviewRequest 对象，包含文件路径和评审参数
    
    Returns:
        StreamingResponse: 流式响应评审结果
    """
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
                tasks.append(asyncio.create_task(process_task(
                    "推理过程", all_text, result_queue, get_markdown_prompt(), 
                    "你是一个专业的论文评审专家，请专注于思考和推理过程，对以下论文进行评审："
                )))
                
                # 添加内容任务
                tasks.append(asyncio.create_task(process_task(
                    "评审内容", all_text, result_queue, get_markdown_prompt(),
                    "你是一个专业的论文评审专家，请专注于评审内容的输出，对以下论文进行评审："
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

# 统一处理任务的辅助函数
async def process_task(task_type, paper_text, result_queue, markdown_prompt, system_prompt):
    """
    统一处理AI评审任务
    
    Args:
        task_type: 任务类型
        paper_text: 论文文本内容
        result_queue: 结果队列
        markdown_prompt: Markdown格式要求
        system_prompt: 系统提示词
    """
    try:
        # 构建系统提示词，添加 Markdown 格式要求
        if markdown_prompt:
            system_prompt = f"你的角色是:\n\n{system_prompt},你的输出格式需要遵循以下要求：{markdown_prompt}"

        print(f"[DEBUG] 开始处理{task_type}任务")
        
        # 创建请求
        response = client.chat.completions.create(
            model="deepseek-r1-250120",
            messages=[
                {"role": "system", "content": system_prompt + paper_text},
            ],
            temperature=0.1,
            stream=True
        )
        
        # 处理响应
        for chunk in response:
            if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                msg_type = "reasoning" if task_type == "推理过程" else "content"
                data = {
                    "type": msg_type,
                    msg_type: content
                }
                await result_queue.put(f"data: {json.dumps(data, ensure_ascii=False)}\n\n")
                await asyncio.sleep(0.001)
        
        # 发送完成信息
        complete_type = "reasoning_complete" if task_type == "推理过程" else "complete"
        complete_msg = {
            "type": complete_type,
            "message": f"{task_type}完成"
        }
        await result_queue.put(f"data: {json.dumps(complete_msg, ensure_ascii=False)}\n\n")
        print(f"[DEBUG] {task_type}任务完成")
        
    except Exception as e:
        import traceback
        print(f"[ERROR] {task_type}处理异常: {str(e)}")
        print(f"[ERROR] {task_type}处理异常堆栈: {traceback.format_exc()}")
        error_msg = {
            "type": "error",
            "message": str(e)
        }
        await result_queue.put(f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n")

# 处理JSON结构化任务的辅助函数        
async def process_json_task(paper_text, result_queue):
    """
    处理JSON结构化任务
    
    Args:
        paper_text: 论文文本内容
        result_queue: 结果队列
    """
    try:
        # 获取JSON提示词
        json_prompt = get_json_prompt()
        if not json_prompt:
            print("[WARNING] 没有找到JSON提示词，无法生成结构化数据")
            error_msg = {
                "type": "error",
                "message": "没有找到JSON提示词，无法生成结构化数据"
            }
            await result_queue.put(f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n")
            return
        
        # 调用模型生成JSON结构
        print("[DEBUG] 开始生成JSON结构化数据")
        response = client.chat.completions.create(
            model="deepseek-r1-250120",
            messages=[
                {"role": "system", "content": json_prompt},
                {"role": "user", "content": f"请从以下论文中提取json结构化信息:\n\n{paper_text}"}
            ],
            temperature=0.1,
            stream=True
        )
        
        full_content = ""
        for chunk in response:
            if hasattr(chunk.choices[0].delta, 'content'):
                content = chunk.choices[0].delta.content
                full_content += content
                json_result = {
                    "type": "json_structure",
                    "json_structure": content
                }
                await result_queue.put(f"data: {json.dumps(json_result, ensure_ascii=False)}\n\n")
                await asyncio.sleep(0.001)
        
        # 输出完整JSON结构
        full_json_result = {
            "type": "json_complete",
            "json_structure": full_content
        }
        await result_queue.put(f"data: {json.dumps(full_json_result, ensure_ascii=False)}\n\n")
        print(f"[DEBUG] JSON结构生成完成")
        
    except Exception as e:
        print(f"[ERROR] 生成JSON结构异常: {str(e)}")
        import traceback
        print(f"[ERROR] JSON结构生成异常堆栈: {traceback.format_exc()}")
        error_msg = {
            "type": "error",
            "message": str(e)
        }
        await result_queue.put(f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n")

def launch_app(host="localhost", port=5555):
    """
    启动论文评审API服务
    
    Args:
        host: 主机地址，默认为127.0.0.1
        port: 端口号，默认为5555
    """
    import uvicorn
    uvicorn.run(app, host=host, port=port)

# 在导入部分后添加读取 Markdown 提示词的函数
def get_markdown_prompt():
    """读取 Markdown 格式化提示词"""
    try:
        prompt_path = os.path.join("doc", "markdown_prompt.md")
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"[ERROR] 读取 Markdown 提示词失败: {str(e)}")
        return ""  # 如果读取失败，返回空字符串，不影响原有功能

if __name__ == "__main__":
    launch_app()
