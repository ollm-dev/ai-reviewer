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
async def extract_json_structure(paper_text):
    """
    从论文内容中提取JSON结构
    
    
    Args:
        paper_text: 论文文本内容
    
    Returns:
        str: JSON格式的结构化数据
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
            yield f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n"
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
                yield f"data: {json.dumps(json_result, ensure_ascii=False)}\n\n"
                print(f"[DEBUG] 生成的JSON结构: {json_result}")
                await asyncio.sleep(0.01)
        full_json_result = {
            "type": "json_complete",
            "json_structure": full_content
        }
        yield f"data: {json.dumps(full_json_result, ensure_ascii=False)}\n\n"
        print(f"[DEBUG] 生成的JSON结构: {full_json_result}")  
        # try:
        #     # 验证JSON格式
        #     # json.loads(json_result)
        #     return json_result
        # except json.JSONDecodeError as json_err:
        #     print(f"[ERROR] 生成的JSON格式不正确: {str(json_err)}")
        #     return "{}"  # 返回空JSON对象
    except Exception as e:
        print(f"[ERROR] 生成JSON结构异常: {str(e)}")
        import traceback
        print(f"[ERROR] JSON结构生成异常堆栈: {traceback.format_exc()}")
        error_msg = {
            "type": "error",
            "message": str(e)
        }
        yield f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n"
        return

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

    async def generate():
        try:
            # 获取 PDF 文件名
            pdf_name = os.path.basename(request.file_path)
            print(f"[DEBUG] 开始处理PDF: {pdf_name}")

            # 用于保存提取的文本
            all_text = ""
            
            try:
                print(f"[DEBUG] 开始读取PDF文件: {request.file_path}")
                with open(request.file_path, 'rb') as file:
                    try:
                        reader = PyPDF2.PdfReader(file)
                        num_pages = len(reader.pages)
                        print(f"[DEBUG] PDF读取成功，共 {num_pages} 页")
                        
                        # 确定要处理的页数
                        pages_to_load = num_pages
                        if request.page_limit > 0 and request.page_limit < num_pages:
                            pages_to_load = request.page_limit
                        
                        # 提取文本
                        for i in range(pages_to_load):
                            print(f"[DEBUG] 正在提取第 {i+1}/{pages_to_load} 页")
                            page = reader.pages[i]
                            text = page.extract_text()
                            all_text += text + "\n\n"
                            # 发送进度信息
                            progress = {
                                "type": "progress",
                                "current": i + 1,
                                "total": pages_to_load,
                                "message": f"正在处理第 {i + 1}/{pages_to_load} 页"
                            }
                            yield f"data: {json.dumps(progress, ensure_ascii=False)}\n\n"
                            await asyncio.sleep(0.03)
                    except Exception as pdf_err:
                        print(f"[ERROR] PDF解析异常: {str(pdf_err)}")
                        import traceback
                        print(f"[ERROR] PDF解析异常堆栈: {traceback.format_exc()}")
                        raise pdf_err
            except Exception as file_err:
                print(f"[ERROR] 文件读取异常: {str(file_err)}")
                import traceback
                print(f"[ERROR] 文件读取异常堆栈: {traceback.format_exc()}")
                error_msg = {
                    "type": "error",
                    "message": f"文件读取失败: {str(file_err)}"
                }
                yield f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n"
                return

            print(f"[DEBUG] 提取的文本示例: {all_text[:100]}...")
            
            # 流式调用API
            print("[DEBUG] 开始调用AI评审API")

            # 获取 Markdown 提示词
            markdown_prompt = get_markdown_prompt()

            # 构建系统提示词，添加 Markdown 格式要求
            system_prompt = "你是一个专业的论文评审专家，请对以下论文进行评审："
            if markdown_prompt:
                system_prompt = f"你的角色是:\n\n{system_prompt},你的输出格式需要遵循以下要求：{markdown_prompt}"

            response = client.chat.completions.create(
                model="deepseek-r1-250120",
                messages=[
                    {"role": "system", "content": system_prompt + all_text},
                ],
                temperature=0.1,
                #max_tokens=8000,
                stream=True
            )
            
            # 处理流式响应
            full_content = ""  # 用于收集完整内容以生成JSON结构
            
            for chunk in response:
                # 获取思考过程和最终回答
                if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[0].delta.reasoning_content:
                    reasoning_content = chunk.choices[0].delta.reasoning_content
                    data = {
                        "type": "reasoning",
                        "reasoning": reasoning_content
                    }
                    print(f"[DEBUG] reasoning: {reasoning_content}")
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    # 添加小延迟确保流式传输效果
                    await asyncio.sleep(0.01)

                if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content  # 收集完整内容
                    data = {
                        "type": "content",
                        "content": content
                    }
                    print(f"[DEBUG] content char: {content}")
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    # 添加小延迟确保流式传输效果
                    await asyncio.sleep(0.01)
                   

            # 发送完成信息
            complete_msg = {
                "type": "complete",
                "message": "评审完成",
            }
            yield f"data: {json.dumps(complete_msg, ensure_ascii=False)}\n\n"

            # json结构 流式输出 和 完整结构输出
            # 使用 async for 而不是 await
            async for json_chunk in extract_json_structure(all_text):
                yield json_chunk
        except Exception as e:
            print(f"[ERROR] 评审处理异常: {str(e)}")
            import traceback
            print(f"[ERROR] 评审处理异常堆栈: {traceback.format_exc()}")
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
        generate(), 
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
