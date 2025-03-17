import openai
import time
import sys
import os
from util.perform_review import load_paper, perform_review
from util.conf import get_conf

conf = get_conf()

API_KEY = conf["model"]["api_key"]
API_BASE = conf["model"]["api_base"]
MODEL = conf["model"]["model"]

# OpenRouter配置
OPENROUTER_API_KEY = conf["openrouter"]["api_key"]
OPENROUTER_API_BASE = conf["openrouter"]["api_base"]
OPENROUTER_MODEL = conf["openrouter"]["model"]
OPENROUTER_SITE_URL = conf["openrouter"]["site_url"]
OPENROUTER_SITE_NAME = conf["openrouter"]["site_name"]


def review_paper(paper_path, api_key=API_KEY, api_base=API_BASE, model=MODEL, 
                use_claude=False, num_reviewers=1, pages=None):
    """
    评审一篇论文
    
    Args:
        paper_path: PDF论文路径
        api_key: OpenAI API密钥
        api_base: API基础URL
        model: 使用的模型名称
        use_claude: 是否使用Claude模型
        num_reviewers: 评审员数量
        pages: 处理的页数限制，None表示处理全部页面
    Returns:
        generator: 生成进度更新和最终结果的生成器
    """
    start_time = time.time()
    
    def update_progress(msg, result=None):
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        log_msg = f"[{timestamp}] {msg}"
        print(f"[DEBUG] {log_msg}", file=sys.stderr)  # 输出到stderr便于调试
        # 向生成器的调用者传递进度更新和结果
        return msg, result
    
    token_stats = {
        'prompt_tokens': 0,
        'completion_tokens': 0,
        'total_tokens': 0,
        'total_cost': 0,
        'input_cost': 0,
        'output_cost': 0
    }
    
    # 根据选择的模型设置API配置
    if use_claude:
        # 向调用者传递进度更新
        msg, _ = update_progress("正在配置Claude 3.7模型...")
        yield msg, None
        print(f"[{time.strftime('%H:%M:%S')}] 正在配置Claude 3.7模型...", file=sys.stderr)
        
        # 设置OpenRouter API
        client = openai.OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_API_BASE,
        )
        model = OPENROUTER_MODEL
        
        # Claude 3.7 Sonnet 定价：$15/百万tokens输入，$75/百万tokens输出
        token_price_input = 15 / 1000000 * 7.2  # 每token人民币价格（假设汇率1:7.2）
        token_price_output = 75 / 1000000 * 7.2  # 每token人民币价格
        exchange_rate = 7.2  # 美元兑人民币汇率
        msg, _ = update_progress("Claude模型配置完成")
        yield msg, None
        print(f"[{time.strftime('%H:%M:%S')}] Claude模型配置完成", file=sys.stderr)
    else:
        # 向调用者传递进度更新
        msg, _ = update_progress("正在配置默认模型...")
        yield msg, None
        print(f"[{time.strftime('%H:%M:%S')}] 正在配置默认模型...", file=sys.stderr)
        
        # 设置默认API
        client = openai.OpenAI(
            api_key=api_key,
            base_url=api_base,
        )
        # GLM-4-Plus 定价：0.05元/千tokens (统一价格)
        token_price_input = 0.05 / 1000  # 每token人民币价格
        token_price_output = 0.05 / 1000  # 每token人民币价格
        exchange_rate = 1.0  # 已经是人民币价格
        msg, _ = update_progress("默认模型配置完成")
        yield msg, None
        print(f"[{time.strftime('%H:%M:%S')}] 默认模型配置完成", file=sys.stderr)
        
    try:
        # 加载论文
        msg, _ = update_progress(f"正在解析PDF内容... (页数限制: {pages if pages else '无限制'})")
        yield msg, None
        print(f"[{time.strftime('%H:%M:%S')}] 正在解析PDF内容... (页数限制: {pages if pages else '无限制'})", file=sys.stderr)
        print(f"[{time.strftime('%H:%M:%S')}] PDF文件路径: {paper_path}", file=sys.stderr)
        
        # 检查文件是否存在
        if isinstance(paper_path, str):
            if os.path.exists(paper_path):
                print(f"[{time.strftime('%H:%M:%S')}] 文件存在，大小: {os.path.getsize(paper_path) / 1024:.2f} KB", file=sys.stderr)
            else:
                error_msg = f"PDF文件不存在: {paper_path}"
                print(f"[{time.strftime('%H:%M:%S')}] {error_msg}", file=sys.stderr)
                msg, _ = update_progress(error_msg)
                yield msg, None
                raise FileNotFoundError(error_msg)
        
        load_start_time = time.time()
        try:
            print(f"[{time.strftime('%H:%M:%S')}] 开始调用load_paper函数...", file=sys.stderr)
            paper_txt = load_paper(paper_path, num_pages=pages)
            print(f"[{time.strftime('%H:%M:%S')}] load_paper函数调用成功", file=sys.stderr)
            load_end_time = time.time()
            load_duration = load_end_time - load_start_time
            word_count = len(paper_txt.split())
            char_count = len(paper_txt)
            msg, _ = update_progress(f"PDF解析完成，耗时 {load_duration:.2f} 秒，共 {word_count} 个单词，{char_count} 个字符")
            yield msg, None
            print(f"[{time.strftime('%H:%M:%S')}] PDF解析完成，耗时 {load_duration:.2f} 秒，共 {word_count} 个单词，{char_count} 个字符", file=sys.stderr)
            
            # 打印PDF内容的前500个字符，用于调试
            print(f"[{time.strftime('%H:%M:%S')}] PDF内容预览 (前500字符):\n{paper_txt[:500]}...", file=sys.stderr)
            
            # 如果文本太长，可能需要截断
            if char_count > 100000:  # 约25000个单词
                msg, _ = update_progress(f"警告：文本过长 ({char_count} 字符)，可能超出模型上下文窗口，将截断...")
                yield msg, None
                print(f"[{time.strftime('%H:%M:%S')}] 警告：文本过长 ({char_count} 字符)，可能超出模型上下文窗口，将截断...", file=sys.stderr)
                paper_txt = paper_txt[:100000]
                msg, _ = update_progress("文本已截断至 100000 字符")
                yield msg, None
                print(f"[{time.strftime('%H:%M:%S')}] 文本已截断至 100000 字符", file=sys.stderr)
        except Exception as e:
            msg, _ = update_progress(f"PDF解析出错: {str(e)}")
            yield msg, None
            print(f"[{time.strftime('%H:%M:%S')}] PDF解析出错: {str(e)}", file=sys.stderr)
            raise e
        
        # 执行评审
        msg, _ = update_progress("开始生成评审意见...")
        yield msg, None
        print(f"[{time.strftime('%H:%M:%S')}] 开始生成评审意见...", file=sys.stderr)
        
        # 创建一个内部进度回调函数，将进度传递给外部
        def internal_progress_callback(msg):
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            print(f"[{timestamp}] 内部进度: {msg}", file=sys.stderr)
            # 不再尝试传递进度消息给外部，因为这会导致问题
            return None
        
        review_start_time = time.time()
        print(f"[{time.strftime('%H:%M:%S')}] 准备调用perform_review函数...", file=sys.stderr)
        
        # 打印当前使用的模型，确认是否正确
        print(f"[{time.strftime('%H:%M:%S')}] 当前使用的模型: {model}", file=sys.stderr)
        
        try:
            result = perform_review(
                paper_txt,
                model=model,
                client=client,
                num_reflections=1,  # 减少反思次数，加快处理
                num_fs_examples=1,
                num_reviews_ensemble=num_reviewers,  # 使用用户指定的评审员数量
                temperature=0.7,
                return_raw_responses=True,  # 返回原始响应
                progress_callback=None  # 不再使用内部回调，避免问题
            )
            
            # 手动传递一个进度更新，确保前端知道评审已完成
            msg, _ = update_progress("评审处理已完成，正在整理结果...")
            yield msg, None
            
            review_end_time = time.time()
            review_duration = review_end_time - review_start_time
            msg, _ = update_progress(f"评审生成完成，耗时 {review_duration:.2f} 秒")
            yield msg, None
            print(f"[{time.strftime('%H:%M:%S')}] 评审生成完成，耗时 {review_duration:.2f} 秒", file=sys.stderr)
            
            if isinstance(result, tuple) and len(result) >= 3:
                review, stats, raw_responses = result
                msg, _ = update_progress("成功获取评审结果、统计信息和原始响应")
                yield msg, None
                print(f"[{time.strftime('%H:%M:%S')}] 成功获取评审结果、统计信息和原始响应", file=sys.stderr)
                
                # 将原始响应传递给前端
                if raw_responses and isinstance(raw_responses, list):
                    for i, raw_response in enumerate(raw_responses):
                        if raw_response:
                            msg, _ = update_progress(f"评审员 {i+1} 原始响应")
                            yield msg, raw_response
                
                # 打印评审结果的关键信息
                if review:
                    msg, _ = update_progress(f"评审结果: 熟悉程度={review.get('熟悉程度', 'N/A')}, 综合评价={review.get('综合评价', 'N/A')}, 资助意见={review.get('资助意见', 'N/A')}")
                    yield msg, None
                    print(f"[{time.strftime('%H:%M:%S')}] 评审结果: 熟悉程度={review.get('熟悉程度', 'N/A')}, 综合评价={review.get('综合评价', 'N/A')}, 资助意见={review.get('资助意见', 'N/A')}", file=sys.stderr)
                    
                    # 添加原始响应到结果中
                    review['raw_responses'] = raw_responses
            elif isinstance(result, tuple):
                review, stats = result
                msg, _ = update_progress("成功获取评审结果和统计信息")
                yield msg, None
                print(f"[{time.strftime('%H:%M:%S')}] 成功获取评审结果和统计信息", file=sys.stderr)
                
                # 打印评审结果的关键信息
                if review:
                    msg, _ = update_progress(f"评审结果: 熟悉程度={review.get('熟悉程度', 'N/A')}, 综合评价={review.get('综合评价', 'N/A')}, 资助意见={review.get('资助意见', 'N/A')}")
                    yield msg, None
                    print(f"[{time.strftime('%H:%M:%S')}] 评审结果: 熟悉程度={review.get('熟悉程度', 'N/A')}, 综合评价={review.get('综合评价', 'N/A')}, 资助意见={review.get('资助意见', 'N/A')}", file=sys.stderr)
            else:
                review = result
                stats = {'prompt_tokens': 0, 'completion_tokens': 0}
                msg, _ = update_progress("警告：未获取到统计信息，使用默认值")
                yield msg, None
                print(f"[{time.strftime('%H:%M:%S')}] 警告：未获取到统计信息，使用默认值", file=sys.stderr)
            
            # 处理None结果的情况
            if review is None:
                msg, _ = update_progress("警告：评审结果为空，创建默认评审结果")
                yield msg, None
                print(f"[{time.strftime('%H:%M:%S')}] 警告：评审结果为空，创建默认评审结果", file=sys.stderr)
                review = {
                    "熟悉程度": "C",
                    "综合评价": "C",
                    "资助意见": "不予资助",
                    "面向需求评价": "评审过程出错，无法评估该项目是否面向经济社会发展需要或国家需求背后的基础科学问题。",
                    "创新性与科学价值评价": "评审过程出错，无法评估该项目的创新性与科学价值。",
                    "研究基础与可行性评价": "评审过程出错，无法评估该项目的研究基础与可行性。",
                    "其他建议": "API返回结果异常，请重试"
                }
                
            if stats is None:
                msg, _ = update_progress("警告：统计信息为空，使用默认值")
                yield msg, None
                print(f"[{time.strftime('%H:%M:%S')}] 警告：统计信息为空，使用默认值", file=sys.stderr)
                stats = {'prompt_tokens': 0, 'completion_tokens': 0}
            
            # 更新token统计
            token_stats['prompt_tokens'] += stats['prompt_tokens']
            token_stats['completion_tokens'] += stats['completion_tokens']
            token_stats['total_tokens'] = (
                token_stats['prompt_tokens'] +
                token_stats['completion_tokens']
            )
            
            # 计算费用 (区分输入和输出token的价格)
            input_cost = token_stats['prompt_tokens'] * token_price_input * exchange_rate
            output_cost = token_stats['completion_tokens'] * token_price_output * exchange_rate
            token_stats['total_cost'] = input_cost + output_cost
            token_stats['input_cost'] = input_cost
            token_stats['output_cost'] = output_cost
            
            token_summary = f"""
Token 使用统计:
- 输入tokens: {token_stats['prompt_tokens']:,}
- 输出tokens: {token_stats['completion_tokens']:,}
- 总计tokens: {token_stats['total_tokens']:,}
- 输入费用: ¥{input_cost:.4f}
- 输出费用: ¥{output_cost:.4f}
- 总计费用: ¥{token_stats['total_cost']:.4f}
"""
            msg, _ = update_progress(token_summary)
            yield msg, None
            print(f"[{time.strftime('%H:%M:%S')}] {token_summary}", file=sys.stderr)
            
            # 添加token统计到结果中
            review['token_stats'] = token_stats
            
            # 计算总耗时
            end_time = time.time()
            total_duration = end_time - start_time
            msg, _ = update_progress(f"整个评审过程完成，总耗时 {total_duration:.2f} 秒")
            yield msg, None
            print(f"[{time.strftime('%H:%M:%S')}] 整个评审过程完成，总耗时 {total_duration:.2f} 秒", file=sys.stderr)
            
            msg, _ = update_progress("返回最终评审结果")
            yield msg, review  # 生成最终结果
                
        except Exception as e:
            import traceback
            error_msg = f"perform_review调用出错: {str(e)}"
            error_traceback = traceback.format_exc()
            print(f"[{time.strftime('%H:%M:%S')}] {error_msg}\n\n{error_traceback}", file=sys.stderr)
            msg, _ = update_progress(error_msg)
            yield msg, None
            
            # 创建一个默认的评审结果
            review = {
                "熟悉程度": "C",
                "综合评价": "C",
                "资助意见": "不予资助",
                "面向需求评价": "评审过程出错，无法评估该项目是否面向经济社会发展需要或国家需求背后的基础科学问题。",
                "创新性与科学价值评价": "评审过程出错，无法评估该项目的创新性与科学价值。",
                "研究基础与可行性评价": "评审过程出错，无法评估该项目的研究基础与可行性。",
                "其他建议": f"API调用出错: {str(e)}"
            }
            stats = {
                'prompt_tokens': 0, 
                'completion_tokens': 0,
                'total_tokens': 0,
                'total_cost': 0,
                'input_cost': 0,
                'output_cost': 0
            }
            
            msg, _ = update_progress("返回默认评审结果")
            yield msg, review  # 返回默认结果
            
    except Exception as e:
        import traceback
        error_msg = f"评审过程出错: {str(e)}"
        error_traceback = traceback.format_exc()
        print(f"[{time.strftime('%H:%M:%S')}] {error_msg}\n\n{error_traceback}", file=sys.stderr)
        msg, _ = update_progress(f"{error_msg}\n\n{error_traceback}")
        yield msg, None
        
        # 创建一个默认的评审结果
        review = {
            "熟悉程度": "C",
            "综合评价": "C",
            "资助意见": "不予资助",
            "面向需求评价": "评审过程出错，无法评估该项目是否面向经济社会发展需要或国家需求背后的基础科学问题。",
            "创新性与科学价值评价": "评审过程出错，无法评估该项目的创新性与科学价值。",
            "研究基础与可行性评价": "评审过程出错，无法评估该项目的研究基础与可行性。",
            "其他建议": f"出错: {str(e)}"
        }
        stats = {
            'prompt_tokens': 0, 
            'completion_tokens': 0,
            'total_tokens': 0,
            'total_cost': 0,
            'input_cost': 0,
            'output_cost': 0
        }
        
        msg, _ = update_progress("返回默认评审结果")
        yield msg, review  # 返回默认结果


if __name__ == "__main__":
    # 设置参数
    PAPER_PATH = ("/Users/dave/ai-reviewer/data/中国农村电子商务发展的区域特征、形成机理及空间效应研究.pdf")
    API_KEY = "sk-e7WU18hiRgR1AvK16c6cAcE89c1143329383E8622fC8F0D5"
    API_BASE = "https://api.fast-tunnel.one/v1"
    
    # 运行评审
    for progress in review_paper(PAPER_PATH, API_KEY, API_BASE, num_pages=20):
        if isinstance(progress, tuple):
            print("评审完成，获取结果")
        else:
            print(f"进度: {progress}")