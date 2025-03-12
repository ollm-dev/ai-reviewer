def load_examples():
    try:
        # 确保使用 UTF-8 编码读取文件
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        print(f"读取示例文件时出错: {str(e)}")
        return None
