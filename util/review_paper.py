import openai
import os
from util.perform_review import load_paper, perform_review
from util.conf import get_conf

conf = get_conf()

API_KEY = conf["model"]["api_key"]
API_BASE = conf["model"]["api_base"]
MODEL = conf["model"]["model"]

def review_paper(paper_path, api_key=API_KEY, api_base=API_BASE, model=MODEL, progress_callback=None):
    """评审一篇论文
    
    Args:
        paper_path: PDF论文路径
        api_key: OpenAI API密钥
        api_base: API基础URL
        model: 使用的模型名称
        progress_callback: 进度回调函数
        
    Returns:
        generator: 生成进度更新和最终结果的生成器
    """
    def update_progress(msg):
        """内部进度更新函数"""
        if progress_callback:
            progress_callback(msg)
        print(f"[Progress] {msg}")  # 保留日志输出
        if progress_callback:
            yield msg  # 使用yield返回进度
    
    token_stats = {
        'prompt_tokens': 0,
        'completion_tokens': 0,
        'total_tokens': 0,
        'total_cost': 0
    }
        
    # 设置API配置
    os.environ["OPENAI_API_KEY"] = api_key
    client = openai.OpenAI(
        api_key=api_key,
        base_url=api_base
    )
    
    try:
        # 加载论文
        yield from update_progress("正在解析PDF内容...")
        paper_txt = load_paper(paper_path)
        
        # 执行评审
        yield from update_progress("开始生成评审意见...")
        
        # 创建一个包装回调函数来处理流式输出
        def stream_callback(msg):
            print(f"[Stream] {msg}")  # 添加流式输出日志
            yield from update_progress(msg)
        
        # 使用流式回调进行评审
        result = perform_review(
            paper_txt,
            model=model,
            client=client,
            num_reflections=5,
            num_fs_examples=1,
            num_reviews_ensemble=5,
            progress_callback=stream_callback  # 传递流式回调
        )
        
        if isinstance(result, tuple):
            review, stats = result
        else:
            review = result
            stats = {'prompt_tokens': 0, 'completion_tokens': 0}
        
        # # 更新token统计
        # token_stats['prompt_tokens'] += stats['prompt_tokens']
        # token_stats['completion_tokens'] += stats['completion_tokens']
        # token_stats['total_tokens'] = (
        #     token_stats['prompt_tokens'] +
        #     token_stats['completion_tokens']
        # )
        # # GLM-4-Plus 定价：0.05元/千tokens
        # token_stats['total_cost'] = token_stats['total_tokens'] * 0.05 / 1000
        
        # stats_msg = (
        #     f"Token 使用统计:\n"
        #     f"- 输入tokens: {token_stats['prompt_tokens']}\n"
        #     f"- 输出tokens: {token_stats['completion_tokens']}\n"
        #     f"- 总计tokens: {token_stats['total_tokens']}\n"
        #     f"- 预估费用: ¥{token_stats['total_cost']:.4f}"
        # )
        # yield stats_msg
        
        save_msg = "保存评审结果..."
        yield save_msg
        
        # 保存评审结果
        output_dir = os.path.dirname(paper_path)
        output_path = os.path.join(output_dir, "review.txt")
        with open(output_path, "w", encoding='utf-8') as f:
            f.write(f"总体评分: {review['Overall']}/10\n")
            f.write(f"决定: {review['Decision']}\n\n")
            f.write("优点:\n")
            for s in review['Strengths']:
                f.write(f"- {s}\n")
            f.write("\n缺点:\n")
            for w in review['Weaknesses']:
                f.write(f"- {w}\n")
            f.write("\n问题:\n")
            for q in review['Questions']:
                f.write(f"- {q}\n")
        
        # 返回最终结果
        yield review, token_stats
            
    except Exception as e:
        error_msg = f"评审过程出错: {str(e)}"
        yield error_msg
        raise e

if __name__ == "__main__":
    # 设置参数
    PAPER_PATH = ("./data/ICAI_Transferability_Prediction_for_Model_Recommendation"
                 "_A_Graph_Learning_Method.pdf")
    API_KEY = "sk-e7WU18hiRgR1AvK16c6cAcE89c1143329383E8622fC8F0D5"
    API_BASE = "https://api.fast-tunnel.one/v1"
    
    # 运行评审
    review_paper(PAPER_PATH, API_KEY, API_BASE)