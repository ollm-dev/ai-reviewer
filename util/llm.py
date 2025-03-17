import json
import re
import time
import sys

import backoff
import openai




MAX_NUM_TOKENS = 4096

# Get N responses from a single message, used for ensembling.
@backoff.on_exception(backoff.expo, (openai.RateLimitError, openai.APITimeoutError))
def get_batch_responses_from_llm(
        msg,
        client,
        model,
        system_message,
        msg_history=None,
        temperature=0.75,
        n_responses=1,
        stream_handler=None,
):
    print(f"[{time.strftime('%H:%M:%S')}] 开始批量获取{n_responses}个响应...", file=sys.stderr)
    if msg_history is None:
        msg_history = []

    content, new_msg_history = [], []
    for i in range(n_responses):
        print(f"[{time.strftime('%H:%M:%S')}] 获取第{i+1}个评审响应...", file=sys.stderr)
        print(f"[{time.strftime('%H:%M:%S')}] 评审员 {i+1}/{n_responses} 开始工作", file=sys.stderr)
        c, hist = get_response_from_llm(
            msg,
            client,
            model,
            system_message,
            msg_history=None,
            temperature=temperature,
            stream_handler=stream_handler,  # 传递流式处理函数
        )
        print(f"[{time.strftime('%H:%M:%S')}] 评审员 {i+1}/{n_responses} 完成评审", file=sys.stderr)
        
        # 打印评审响应的前100个字符
        preview = c[:100].replace('\n', ' ')
        print(f"[{time.strftime('%H:%M:%S')}] 评审员 {i+1} 响应预览: {preview}...", file=sys.stderr)
        
        # 如果有流式处理函数，传递完整响应
        if stream_handler:
            stream_handler(c)
        
        content.append(c)
        new_msg_history.append(hist)

    print(f"[{time.strftime('%H:%M:%S')}] 所有{n_responses}个评审员已完成评审", file=sys.stderr)
    return content, new_msg_history


@backoff.on_exception(backoff.expo, (openai.RateLimitError, openai.APITimeoutError))
def get_response_from_llm(
        msg,
        client,
        model,
        system_message,
        msg_history=None,
        temperature=0.75,
        stream_handler=None,
):
    print(f"[{time.strftime('%H:%M:%S')}] 开始获取LLM响应，模型: {model}", file=sys.stderr)
    if msg_history is None:
        msg_history = []

    new_msg_history = msg_history + [{"role": "user", "content": msg}]
    
    # 打印提示词的长度信息
    prompt_length = len(msg)
    print(f"[{time.strftime('%H:%M:%S')}] 提示词长度: {prompt_length} 字符", file=sys.stderr)
    
    # 根据模型类型选择不同的API调用方式
    try:
        print(f"[{time.strftime('%H:%M:%S')}] 准备调用API...", file=sys.stderr)
        start_time = time.time()
        
        if "deepseek-r1" in model.lower():
            print(f"[{time.strftime('%H:%M:%S')}] 使用DeepSeek-R1模型", file=sys.stderr)
            
            # 是否使用流式输出
            if stream_handler:
                # 流式输出
                content_buffer = ""
                reasoning_buffer = ""
                
                def process_stream(chunk):
                    nonlocal content_buffer, reasoning_buffer
                    
                    # 处理思考过程
                    if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[0].delta.reasoning_content:
                        reasoning_part = chunk.choices[0].delta.reasoning_content
                        reasoning_buffer += reasoning_part
                        # 显示思考过程（黄色文本）
                        print(f"\033[33m{reasoning_part}\033[0m", end="", flush=True)
                        # 记录原始思考过程内容（不带颜色）
                        print(f"[思考过程] {reasoning_part}", file=sys.stderr)
                        # 调用stream_handler，直接传递思考过程内容，不添加标签
                        if stream_handler:
                            # 每次收到思考过程内容就立即传递给stream_handler
                            stream_handler(reasoning_part)
                    
                    # 处理最终回答
                    if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                        content_part = chunk.choices[0].delta.content
                        content_buffer += content_part
                        # 显示最终回答（绿色文本）
                        print(f"\033[32m{content_part}\033[0m", end="", flush=True)
                        # 记录原始最终回答内容（不带颜色）
                        print(f"[最终回答] {content_part}", file=sys.stderr)
                        # 调用stream_handler，直接传递最终回答内容，不添加标签
                        if stream_handler:
                            # 每次收到最终回答内容就立即传递给stream_handler
                            stream_handler(content_part)
                
                # 流式调用API
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_message},
                        *new_msg_history,
                    ],
                    temperature=temperature,
                    max_tokens=MAX_NUM_TOKENS,
                    stream=True
                )
                
                # 处理流式响应
                for chunk in response:
                    process_stream(chunk)
                
                # 如果思考过程为空，可能是API不支持或模型没有生成
                if not reasoning_buffer:
                    print(f"[{time.strftime('%H:%M:%S')}] 注意：未收到思考过程", file=sys.stderr)
                
                content = content_buffer
                # 在完整响应中包含思考过程
                if reasoning_buffer:
                    print(f"\n[{time.strftime('%H:%M:%S')}] 思考过程长度: {len(reasoning_buffer)} 字符", file=sys.stderr)
                    # 可以选择是否将思考过程添加到最终内容中
                    # content = f"思考过程:\n{reasoning_buffer}\n\n最终回答:\n{content_buffer}"
                
                # 只在完成后调用一次stream_handler
                if stream_handler:
                    stream_handler("模型已完成响应")
            else:
                # 非流式输出
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_message},
                        *new_msg_history,
                    ],
                    temperature=temperature,
                    max_tokens=MAX_NUM_TOKENS
                )
                
                # 获取思考过程和最终回答
                reasoning_content = ""
                if hasattr(response.choices[0].message, 'reasoning_content'):
                    reasoning_content = response.choices[0].message.reasoning_content
                    print(f"[{time.strftime('%H:%M:%S')}] 思考过程长度: {len(reasoning_content)} 字符", file=sys.stderr)
                
                content = response.choices[0].message.content
                
                # 可以选择是否将思考过程添加到最终内容中
                # if reasoning_content:
                #     content = f"思考过程:\n{reasoning_content}\n\n最终回答:\n{content}"
                
        elif model == "glm-4-plus":
            print(f"[{time.strftime('%H:%M:%S')}] 使用智谱GLM-4-Plus模型", file=sys.stderr)
            
            # 是否使用流式输出
            if stream_handler:
                # 流式输出
                content_buffer = ""
                
                def process_stream(chunk):
                    nonlocal content_buffer
                    if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                        content_piece = chunk.choices[0].delta.content
                        content_buffer += content_piece
                        # 不再每个token都调用stream_handler
                        # stream_handler("模型正在生成", content_piece)
                

                
                # 处理流式响应
                for chunk in response:
                    process_stream(chunk)
                
                content = content_buffer
                # 只在完成后调用一次stream_handler
                if stream_handler:
                    stream_handler("模型已完成响应", content)
                
        elif "claude" in model.lower():
            print(
                f"[{time.strftime('%H:%M:%S')}] 使用Claude模型通过OpenRouter", 
                file=sys.stderr
            )
            
            # 确保使用正确的模型格式
            openrouter_model = "anthropic/claude-3.7-sonnet:beta"
            print(
                f"[{time.strftime('%H:%M:%S')}] 使用OpenRouter模型: {openrouter_model}", 
                file=sys.stderr
            )
            
            # 是否使用流式输出
            if stream_handler:
                # 流式输出
                content_buffer = ""
                
                def process_stream(line):
                    nonlocal content_buffer
                    if not line:
                        return
                    
                    try:
                        # 尝试解析行数据
                        line_text = line.decode('utf-8')
                        if line_text.startswith('data: '):
                            line_text = line_text[6:]  # 移除 'data: ' 前缀
                            
                        if line_text.strip() == '[DONE]':
                            return
                            
                        data = json.loads(line_text)
                        if 'choices' in data and len(data['choices']) > 0:
                            delta = data['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                content_buffer += content
                    except Exception as e:
                        print(
                            f"[{time.strftime('%H:%M:%S')}] 流式处理错误: {str(e)}", 
                            file=sys.stderr
                        )
                
                # 流式调用API
                try:
                    response_stream = client.chat.completions.create(
                        model=openrouter_model,
                        messages=[
                            {"role": "system", "content": system_message},
                            *new_msg_history,
                        ],
                        temperature=temperature,
                        max_tokens=MAX_NUM_TOKENS,
                        stream=True
                    )
                    
                    # 处理流式响应
                    for line in response_stream:
                        process_stream(line)
                    
                    content = content_buffer
                    # 只在完成后调用一次stream_handler
                    if stream_handler:
                        stream_handler("模型已完成响应", content)
                except Exception as e:
                    print(
                        f"[{time.strftime('%H:%M:%S')}] 流式API调用错误: {str(e)}", 
                        file=sys.stderr
                    )
                    raise e
            else:
                # 非流式输出
                response = client.chat.completions.create(
                    model=openrouter_model,
                    messages=[
                        {"role": "system", "content": system_message},
                        *new_msg_history,
                    ],
                    temperature=temperature,
                    max_tokens=MAX_NUM_TOKENS
                )
                content = response.choices[0].message.content
                
        else:
            print(f"[{time.strftime('%H:%M:%S')}] 使用默认模型: {model}", file=sys.stderr)
            
            # 是否使用流式输出
            if stream_handler:
                # 流式输出
                content_buffer = ""
                
                def process_stream(chunk):
                    nonlocal content_buffer
                    if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                        content_piece = chunk.choices[0].delta.content
                        content_buffer += content_piece
                        # 不再每个token都调用stream_handler
                        # stream_handler("模型正在生成", content_piece)
                
                # 流式调用API
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_message},
                        *new_msg_history,
                    ],
                    temperature=temperature,
                    max_tokens=MAX_NUM_TOKENS,
                    stream=True
                )
                
                # 处理流式响应
                for chunk in response:
                    process_stream(chunk)
                
                content = content_buffer
                # 只在完成后调用一次stream_handler
                if stream_handler:
                    stream_handler("模型已完成响应", content)
            else:
                # 非流式输出
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_message},
                        *new_msg_history,
                    ],
                    temperature=temperature,
                    max_tokens=MAX_NUM_TOKENS
                )
                content = response.choices[0].message.content
        
        end_time = time.time()
        duration = end_time - start_time
        print(f"[{time.strftime('%H:%M:%S')}] API调用完成，耗时: {duration:.2f}秒", file=sys.stderr)
        
        # 打印响应长度
        response_length = len(content)
        print(f"[{time.strftime('%H:%M:%S')}] 响应长度: {response_length} 字符", file=sys.stderr)
        
        # 打印响应的前200个字符
        preview = content[:200].replace('\n', ' ')
        print(f"[{time.strftime('%H:%M:%S')}] 响应预览: {preview}...", file=sys.stderr)
        
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] API调用出错: {str(e)}", file=sys.stderr)
        raise e
    
    new_msg_history = new_msg_history + [{"role": "assistant", "content": content}]
    
    # 添加使用情况信息
    usage = getattr(response, 'usage', None)
    if usage:
        new_msg_history[-1]["usage"] = {
            "prompt_tokens": getattr(usage, 'prompt_tokens', 0),
            "completion_tokens": getattr(usage, 'completion_tokens', 0),
            "total_tokens": getattr(usage, 'total_tokens', 0)
        }
    else:
        # 如果没有usage信息，估算token数量
        new_msg_history[-1]["usage"] = {
            "prompt_tokens": len(msg) // 4,  # 粗略估计
            "completion_tokens": len(content) // 4,  # 粗略估计
            "total_tokens": (len(msg) + len(content)) // 4  # 粗略估计
        }

    return content, new_msg_history


def extract_json_between_markers(llm_output):
    print(f"[{time.strftime('%H:%M:%S')}] 开始从输出中提取JSON", file=sys.stderr)
    # Regular expression pattern to find JSON content between ```json and ```
    json_pattern = r"```json(.*?)```"
    matches = re.findall(json_pattern, llm_output, re.DOTALL)

    if not matches:
        print(f"[{time.strftime('%H:%M:%S')}] 未找到```json```标记，尝试其他模式", file=sys.stderr)
        # Fallback: Try to find any JSON-like content in the output
        json_pattern = r"\{.*?\}"
        matches = re.findall(json_pattern, llm_output, re.DOTALL)

    for i, json_string in enumerate(matches):
        print(f"[{time.strftime('%H:%M:%S')}] 尝试解析第{i+1}个匹配项", file=sys.stderr)
        json_string = json_string.strip()
        try:
            parsed_json = json.loads(json_string)
            print(f"[{time.strftime('%H:%M:%S')}] 成功解析JSON", file=sys.stderr)
            return parsed_json
        except json.JSONDecodeError:
            print(f"[{time.strftime('%H:%M:%S')}] JSON解析失败，尝试修复", file=sys.stderr)
            # Attempt to fix common JSON issues
            try:
                # Remove invalid control characters
                json_string_clean = re.sub(r"[\x00-\x1F\x7F]", "", json_string)
                parsed_json = json.loads(json_string_clean)
                print(f"[{time.strftime('%H:%M:%S')}] 修复后成功解析JSON", file=sys.stderr)
                return parsed_json
            except json.JSONDecodeError:
                print(f"[{time.strftime('%H:%M:%S')}] 修复后仍解析失败", file=sys.stderr)
                continue  # Try next match

    print(f"[{time.strftime('%H:%M:%S')}] 未找到有效的JSON", file=sys.stderr)
    return None  # No valid JSON found

