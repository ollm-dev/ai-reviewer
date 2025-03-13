import json
import re

import backoff
import openai
from zhipuai import ZhipuAI

zpai_client = ZhipuAI(api_key="45336a2d0f934cde8e11c80f726e4ab9.eIKUaQn3KGOKjq88") 

MAX_NUM_TOKENS = 4096

# 添加流式输出支持
@backoff.on_exception(backoff.expo, (openai.RateLimitError, openai.APITimeoutError))
def get_streaming_response_from_llm(
        msg,
        client,
        model,
        system_message,
        msg_history=None,
        temperature=0.75,
        stream_callback=None
):
    """获取LLM的流式响应
    
    Args:
        msg: 用户消息
        client: API客户端
        model: 模型名称
        system_message: 系统提示
        msg_history: 消息历史
        temperature: 温度参数
        stream_callback: 流式回调函数
        
    Returns:
        tuple: 完整响应内容和更新后的消息历史
    """
    if msg_history is None:
        msg_history = []

    new_msg_history = msg_history + [{"role": "user", "content": msg}]
    
    # 创建流式响应
    response = zpai_client.chat.completions.create(
        model="glm-4-plus",
        messages=[
            {"role": "system", "content": system_message},
            *new_msg_history,
        ],
        temperature=temperature,
        max_tokens=MAX_NUM_TOKENS,
        stream=True  # 启用流式输出
    )
    
    # 收集完整响应
    full_content = ""
    
    # 处理流式响应
    for chunk in response:
        if chunk.choices and len(chunk.choices) > 0:
            content_delta = chunk.choices[0].delta.content
            if content_delta:
                full_content += content_delta
                print(f"[LLM Stream] {content_delta}")  # 添加LLM流式输出日志
                if stream_callback:
                    stream_callback(content_delta, full_content)
    
    # 更新消息历史
    new_msg_history = new_msg_history + [{"role": "assistant", "content": full_content}]
    
    return full_content, new_msg_history

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
        stream_callback=None
):
    """获取多个LLM响应用于集成
    
    Args:
        msg: 用户消息
        client: API客户端
        model: 模型名称
        system_message: 系统提示
        msg_history: 消息历史
        temperature: 温度参数
        n_responses: 响应数量
        stream_callback: 流式回调函数
        
    Returns:
        tuple: 响应内容列表和消息历史列表
    """
    if msg_history is None:
        msg_history = []

    content, new_msg_history = [], []
    for i in range(n_responses):
        # 为每个评审者创建一个包装回调
        def reviewer_callback(delta, full):
            if stream_callback:
                stream_callback(f"评审者 {i+1} 的思考过程:\n{full}")
        
        if stream_callback:
            stream_callback(f"开始生成评审者 {i+1} 的评审...")
            
        # 使用流式API
        c, hist = get_streaming_response_from_llm(
            msg,
            client,
            model,
            system_message,
            msg_history=None,
            temperature=temperature,
            stream_callback=reviewer_callback
        )
        content.append(c)
        new_msg_history.append(hist)

    return content, new_msg_history


@backoff.on_exception(backoff.expo, (openai.RateLimitError, openai.APITimeoutError))
def get_response_from_llm(
        msg,
        client,
        model,
        system_message,
        msg_history=None,
        temperature=0.75,
        stream_callback=None
):
    """获取LLM响应
    
    Args:
        msg: 用户消息
        client: API客户端
        model: 模型名称
        system_message: 系统提示
        msg_history: 消息历史
        temperature: 温度参数
        stream_callback: 流式回调函数
        
    Returns:
        tuple: 响应内容和更新后的消息历史
    """
    # 如果提供了流式回调，使用流式API
    if stream_callback:
        return get_streaming_response_from_llm(
            msg, client, model, system_message, 
            msg_history, temperature, stream_callback
        )
    
    # 否则使用非流式API
    if msg_history is None:
        msg_history = []

    new_msg_history = msg_history + [{"role": "user", "content": msg}]
    response = zpai_client.chat.completions.create(
        model="glm-4-plus",
        messages=[
            {"role": "system", "content": system_message},
            *new_msg_history,
        ],
        temperature=temperature,
        max_tokens=MAX_NUM_TOKENS
    )
    content = response.choices[0].message.content
    new_msg_history = new_msg_history + [{"role": "assistant", "content": content}]

    return content, new_msg_history


def extract_json_between_markers(llm_output):
    """从LLM输出中提取JSON内容
    
    Args:
        llm_output: LLM输出文本
        
    Returns:
        object|None: 解析后的JSON对象或None
    """
    # Regular expression pattern to find JSON content between ```json and ```