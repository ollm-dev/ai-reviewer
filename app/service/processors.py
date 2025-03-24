import json
import asyncio
import openai
from utils.get_prompt import get_json_prompt
from utils.conf import get_conf

# 获取配置
conf = get_conf()

# 创建 OpenAI 客户端
client = openai.OpenAI(
  api_key=conf["model"]["api_key"],
  base_url=conf["model"]["api_base"]
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
        
        # 优化：批量处理响应以减少频繁的队列操作
        batch_size = 3  # 批量处理大小
        batch_content = ""
        
        if task_type == "推理过程":
            # 处理响应
            for chunk in response:
                if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    batch_content += content
                    
                    # 当批量内容达到一定大小或已经是最后一个块时才推送
                    if len(batch_content) >= batch_size:
                        data = {
                            "type": "content",
                            "content": batch_content
                        }
                        await result_queue.put(f"data: {json.dumps(data, ensure_ascii=False)}\n\n")
                        batch_content = ""  # 重置批量内容
                        # 更小的sleep时间，减少延迟
                        await asyncio.sleep(0.0005)
            
            # 发送剩余的内容
            if batch_content:
                data = {
                    "type": "content",
                    "content": batch_content
                }
                await result_queue.put(f"data: {json.dumps(data, ensure_ascii=False)}\n\n")

        elif task_type == "评审内容":
            # 处理响应
            for chunk in response:
                if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[0].delta.reasoning_content:
                    content = chunk.choices[0].delta.reasoning_content
                    batch_content += content
                    
                    # 当批量内容达到一定大小或已经是最后一个块时才推送
                    if len(batch_content) >= batch_size:
                        data = {
                            "type": "reasoning",
                            "reasoning": batch_content
                        }
                        await result_queue.put(f"data: {json.dumps(data, ensure_ascii=False)}\n\n")
                        batch_content = ""  # 重置批量内容
                        # 更小的sleep时间，减少延迟
                        await asyncio.sleep(0.0005)
            
            # 发送剩余的内容
            if batch_content:
                data = {
                    "type": "reasoning",
                    "reasoning": batch_content
                }
                await result_queue.put(f"data: {json.dumps(data, ensure_ascii=False)}\n\n")
            
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

# 专门处理推理过程的函数
async def process_reasoning_task(paper_text, result_queue, markdown_prompt=None):
    """
    处理论文推理过程任务
    
    Args:
        paper_text: 论文文本内容
        result_queue: 结果队列
        markdown_prompt: Markdown格式要求
    """
    system_prompt = "你是一个专业的论文评审专家，请专注于思考和推理过程，对以下论文进行评审："
    await process_task("推理过程", paper_text, result_queue, markdown_prompt, system_prompt)

# 专门处理评审内容的函数
async def process_content_task(paper_text, result_queue, markdown_prompt=None):
    """
    处理论文评审内容任务
    
    Args:
        paper_text: 论文文本内容
        result_queue: 结果队列
        markdown_prompt: Markdown格式要求
    """
    system_prompt = "你是一个专业的论文评审专家，请专注于评审内容的输出，对以下论文进行评审："
    await process_task("评审内容", paper_text, result_queue, markdown_prompt, system_prompt)

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
                {"role": "user", "content": f"请从以下论文中提取json结构化信息 , 务必注意json的格式！！！！:\n\n{paper_text}"}
            ],
            temperature=0.1,
            stream=True
        )
        
        full_content = ""
        batch_content = ""
        batch_size = 10  # JSON内容可以使用更大的批量大小
        
        for chunk in response:
            if hasattr(chunk.choices[0].delta, 'content'):
                content = chunk.choices[0].delta.content
                full_content += content
                batch_content += content
                
                # 当批量内容达到一定大小时才推送
                if len(batch_content) >= batch_size:
                    json_result = {
                        "type": "json_structure",
                        "json_structure": batch_content
                    }
                    await result_queue.put(f"data: {json.dumps(json_result, ensure_ascii=False)}\n\n")
                    batch_content = ""  # 重置批量内容
                    # 更小的sleep时间，减少延迟
                    await asyncio.sleep(0.0005)
        
        # 发送剩余的内容
        if batch_content:
            json_result = {
                "type": "json_structure",
                "json_structure": batch_content
            }
            await result_queue.put(f"data: {json.dumps(json_result, ensure_ascii=False)}\n\n")
        
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