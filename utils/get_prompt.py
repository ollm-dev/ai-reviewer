import os

def get_json_prompt():
    """读取 JSON 格式化提示词"""
    try:
        prompt_path = os.path.join("doc", "Josn_prompt.md")
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"[ERROR] 读取 JSON 提示词失败: {str(e)}")
        return ""  # 如果读取失败，返回空字符串，不影响原有功能

def get_markdown_prompt():
    """读取 Markdown 格式化提示词"""
    try:
        prompt_path = os.path.join("doc", "markdown_prompt.md")
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"[ERROR] 读取 Markdown 提示词失败: {str(e)}")
        return ""  # 如果读取失败，返回空字符串，不影响原有功能 