import os
import json
import asyncio
import PyPDF2

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