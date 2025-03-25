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
            temperature=0.6,
            max_tokens=10000,
            stream=True
        )
        
        
        
        if task_type == "content":
            # 处理响应
            for chunk in response:
                if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                 
                
                    data = {
                        "type": "content",
                        "content": content
                    }
                    await result_queue.put(f"data: {json.dumps(data, ensure_ascii=False)}\n\n")
                  
                    await asyncio.sleep(0.0005)
               # 输出完整JSON结构
            content_result = {
                "type": "content_complete",
                "content_complete": "论文评审完成"
            }
            await result_queue.put(f"data: {json.dumps(content_result, ensure_ascii=False)}\n\n")  
          
        elif task_type == "reasoning":
            # 处理响应
            for chunk in response:
                if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[0].delta.reasoning_content:
                    content = chunk.choices[0].delta.reasoning_content
                  
                    data = {
                        "type": "reasoning",
                        "reasoning": content
                    }
                    await result_queue.put(f"data: {json.dumps(data, ensure_ascii=False)}\n\n")
                    # 更小的sleep时间，减少延迟
                    await asyncio.sleep(0.0005)
            # 输出完整JSON结构
            reasoning_result = {
                "type": "reasoning_complete",
                "reasoning_complete": "论文评审完成"
            }
            await result_queue.put(f"data: {json.dumps(reasoning_result, ensure_ascii=False)}\n\n")  
            

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
    await process_task("reasoning", paper_text, result_queue, markdown_prompt, system_prompt)

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
    await process_task("content", paper_text, result_queue, markdown_prompt, system_prompt)

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
            temperature=0.5,
            max_tokens=10000,
            stream=True
        )
        
        full_content = ""
      
        
        for chunk in response:
            if hasattr(chunk.choices[0].delta, 'content'):
                content = chunk.choices[0].delta.content
                if content is not None:
                    full_content += content
              
                    json_result = {
                        "type": "json_structure",
                        "json_structure": content
                    }
                    await result_queue.put(f"data: {json.dumps(json_result, ensure_ascii=False)}\n\n")
              
                    await asyncio.sleep(0.0005)
        
        # 输出完整JSON结构
        json_result = {
            "type": "json_complete",
            "json_complete": full_content
        }
        await result_queue.put(f"data: {json.dumps(json_result, ensure_ascii=False)}\n\n")
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