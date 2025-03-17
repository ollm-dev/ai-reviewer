import os
import json
from pypdf import PdfReader
import pymupdf4llm
from util.llm import (
    get_response_from_llm,
    get_batch_responses_from_llm,
    extract_json_between_markers,
)
import time
import sys
import traceback

reviewer_system_prompt_base = (
    "你是一个资深的国家基金委项目评审的专业教授，拥有丰富的科研经验和评审经验。"
    "你正在审阅一个提交给中国国家自然科学基金委员会的国家自然科学基金项目申请。"
    "你需要从创新性、科学价值、研究基础、研究方案可行性、研究条件、预期成果和申请经费合理性等方面进行全面评价。"
    "在做出评价时要保持批判性和谨慎性，所有评价必须有充分依据，避免主观臆断。"
    "请记住，你的评审意见将直接影响项目是否获得资助，因此必须公正、客观、负责任。"
)

reviewer_system_prompt_neg = (
    reviewer_system_prompt_base
    + "如果一个项目存在明显缺陷或者你对其价值存疑，应给予中或差的评价并建议不予资助。"
)

reviewer_system_prompt_pos = (
    reviewer_system_prompt_base
    + "如果一个项目具有明显优势或者你认为其具有重要价值，应给予优或良的评价并建议优先资助或可资助。"
)

template_instructions = """
请按照以下格式回复：

思考过程：
<思考过程>

评审意见JSON：
```json
<JSON>
```

在<思考过程>部分，请简要讨论您对该项目的评价理由和思考过程。
详细说明您的高层次论点、必要的选择和评审的预期结果。
不要在这里做泛泛而论的评论，而是针对当前项目进行具体分析。
将此视为您评审的思考阶段。

在<JSON>部分，请以JSON格式提供评审意见，包含以下字段（按顺序）：
- "面向需求评价": 评述该申请项目是否面向经济社会发展需要或国家需求背后的基础科学问题，详细阐述判断理由。
- "创新性与科学价值评价": 评述申请项目所提出的科学问题的创新性与预期成果的科学价值。
- "研究基础与可行性评价": 评述该申请项目的研究基础与可行性，如有可能，对完善研究方案提出建议。
- "其他建议": 其他建议或意见。
- "熟悉程度": 选择A、B、C（熟悉、较熟悉、不熟悉）。
- "综合评价": 选择A、B、C、D（优、良、中、差）。
- "资助意见": 选择A、B、C（优先资助、可资助、不予资助）。

请注意，"综合评价"中的"优"与"资助意见"中的"优先资助"关联；
"综合评价"中的"良"与"资助意见"中的"优先资助"和"可资助"关联；
"综合评价"中的"中"、"差"与"资助意见"中的"不予资助"关联。

此JSON将被自动解析，因此请确保格式准确。
"""

nsfc_form = (
    """
## 国家自然科学基金项目通讯评审意见表

以下是您在评审国家自然科学基金项目时需要考虑的问题和指南。
请记住，您的评审意见对项目的资助决策有重要影响，请保持客观、公正和严谨。

1. 评议指标：
   - 熟悉程度：您对申请内容的熟悉程度（A-熟悉，B-较熟悉，C-不熟悉）
   - 综合评价：对项目的总体评价（A-优，B-良，C-中，D-差）
   - 资助意见：您对项目的资助建议（A-优先资助，B-可资助，C-不予资助）

2. 具体评价意见：
   
   一、请评述该申请项目是否面向经济社会发展需要或国家需求背后的基础科学问题。请详细阐述判断理由。
   
   二、请评述申请项目所提出的科学问题的创新性与预期成果的科学价值。
   
   三、请评述该申请项目的研究基础与可行性；如有可能，请对完善研究方案提出建议。
   
   四、其他建议
"""
    + template_instructions
)


def perform_review(
    text,
    model,
    client,
    num_reflections=1,
    num_fs_examples=1,
    num_reviews_ensemble=1,
    temperature=0.75,
    msg_history=None,
    return_msg_history=False,
    reviewer_system_prompt=reviewer_system_prompt_neg,
    review_instruction_form=nsfc_form,
    progress_callback=None,
    return_raw_responses=False,
):
    """
    对文本进行评审
    
    Args:
        text: 要评审的文本
        model: 使用的模型
        client: API客户端
        num_reflections: 反思次数
        num_fs_examples: 少样本示例数量
        num_reviews_ensemble: 集成评审数量
        temperature: 温度参数
        msg_history: 消息历史
        return_msg_history: 是否返回消息历史
        reviewer_system_prompt: 评审员系统提示词
        review_instruction_form: 评审指导表单
        progress_callback: 进度回调函数
        return_raw_responses: 是否返回原始响应
        
    Returns:
        如果return_raw_responses为True，返回(review, stats, raw_responses)
        否则返回(review, stats)
    """
    def update_progress(msg, raw_response=None):
        """更新进度并传递原始响应"""
        if progress_callback:
            result = progress_callback(msg)
            # 如果有原始响应，也传递给回调函数
            if raw_response:
                try:
                    if hasattr(progress_callback, '__next__'):
                        progress_callback(raw_response)
                    else:
                        # 直接返回原始响应，让调用者处理
                        return raw_response
                except Exception as e:
                    print(f"传递原始响应时出错: {str(e)}")
            return result
        else:
            print(msg)
            if raw_response:
                print(raw_response)
            return msg
    
    update_progress("开始评审过程...")
    
    if msg_history is None:
        msg_history = []
    
    # 准备提示词
    update_progress("准备评审提示词...")
    
    # 获取少样本示例
    fewshot_prompt = get_review_fewshot_examples(num_fs_examples)
    
    # 构建评审提示词
    prompt = f"""
我需要你帮我评审一篇国家自然科学基金申请书。请根据以下内容进行评审：

{review_instruction_form}

以下是申请书内容：

{text}

{fewshot_prompt}

请按照上述评审表格的要求，对这篇申请书进行全面评审。
"""
    
    update_progress("开始生成评审...")
    
    # 获取多个评审结果
    llm_review, msg_histories = get_batch_responses_from_llm(
        prompt,
        client,
        model,
        reviewer_system_prompt,
        msg_history=msg_history,
        temperature=temperature,
        n_responses=num_reviews_ensemble,
        stream_handler=update_progress  # 传递流式处理函数
    )
    
    # 保存原始响应
    raw_responses = llm_review.copy() if return_raw_responses else None
    
    # 将原始响应传递给前端
    if raw_responses:
        for i, response in enumerate(raw_responses):
            update_progress(f"评审员 {i+1} 原始响应", response)
    
    # 解析评审结果
    update_progress("解析评审结果...")
    
    try:
        # 解析每个评审结果
        parsed_reviews = []
        for idx, rev in enumerate(llm_review):
            try:
                update_progress(f"解析第{idx+1}个评审...")
                parsed_review = extract_json_between_markers(rev)
                if parsed_review:
                    parsed_reviews.append(parsed_review)
                    update_progress(f"成功解析第{idx+1}个评审")
                else:
                    update_progress(f"第{idx+1}个评审解析失败：未找到有效JSON")
            except Exception as e:
                update_progress(f"第{idx+1}个评审解析失败：{str(e)}")
            
        parsed_reviews = [r for r in parsed_reviews if r is not None]
        if not parsed_reviews:
            update_progress("所有评审解析失败，无法继续")
            return None, None
            
        update_progress("开始生成元评审...")
        review = get_meta_review(model, client, temperature, parsed_reviews, stream_handler=update_progress)
        update_progress("元评审生成完成")

        # take first valid in case meta-reviewer fails
        if review is None:
            update_progress("元评审生成失败，使用第一个有效评审")
            review = parsed_reviews[0]

        # Replace numerical scores with the average of the ensemble.
        for score, limits in [
            ("Originality", (1, 4)),
            ("Quality", (1, 4)),
            ("Clarity", (1, 4)),
            ("Significance", (1, 4)),
            ("Soundness", (1, 4)),
            ("Presentation", (1, 4)),
            ("Contribution", (1, 4)),
            ("Overall", (1, 10)),
            ("Confidence", (1, 5)),
        ]:
            scores = []
            for r in parsed_reviews:
                if score in r and isinstance(r[score], (int, float)):
                    scores.append(r[score])
            if scores:
                review[score] = sum(scores) / len(scores)
                update_progress(f"计算{score}平均分: {review[score]}")

        # Rewrite the message history with the valid one and new aggregated review.
        update_progress("更新消息历史...")
        msg_history = msg_histories[0][:-1]
        msg_history += [
            {
                "role": "assistant",
                "content": f"""
THOUGHT:
I will start by aggregating the opinions of {num_reviews_ensemble} reviewers that I previously obtained.

REVIEW JSON:
```json
{json.dumps(review, indent=2)}
```
"""
            }
        ]
        
        # 计算token统计
        update_progress("计算token统计...")
        try:
            # 尝试计算token统计
            prompt_tokens = 0
            completion_tokens = 0
            
            # 检查msg_histories的类型和结构
            if isinstance(msg_histories, list):
                for h in msg_histories:
                    if isinstance(h, dict) and "usage" in h:
                        prompt_tokens += h.get("usage", {}).get("prompt_tokens", 0)
                        completion_tokens += h.get("usage", {}).get("completion_tokens", 0)
                    elif isinstance(h, list):
                        # 如果h是列表，尝试遍历其中的字典
                        for item in h:
                            if isinstance(item, dict) and "usage" in item:
                                prompt_tokens += item.get("usage", {}).get("prompt_tokens", 0)
                                completion_tokens += item.get("usage", {}).get("completion_tokens", 0)
            
            total_tokens = prompt_tokens + completion_tokens
        except Exception as e:
            update_progress(f"计算token统计时出错: {str(e)}，使用默认值")
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
        
        stats = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        
        update_progress("评审完成")
        
        if return_raw_responses:
            return review, stats, raw_responses
        else:
            return review, stats
        
    except Exception as e:
        update_progress(f"评审过程出错: {str(e)}")
        update_progress(traceback.format_exc())
        return None, None


reviewer_reflection_prompt = """Round {current_round}/{num_reflections}.
In your thoughts, first carefully consider the accuracy and soundness of the review you just created.
Include any other factors that you think are important in evaluating the paper.
Ensure the review is clear and concise, and the JSON is in the correct format.
Do not make things overly complicated.
In the next attempt, try and refine and improve your review.
Stick to the spirit of the original review unless there are glaring issues.

Respond in the same format as before:
THOUGHT:
<THOUGHT>

REVIEW JSON:
```json
<JSON>
```

If there is nothing to improve, simply repeat the previous JSON EXACTLY after the thought and include "I am done" at the end of the thoughts but before the JSON.
ONLY INCLUDE "I am done" IF YOU ARE MAKING NO MORE CHANGES."""


def load_paper(pdf_path, num_pages=None, min_size=100):
    """
    加载PDF文件并提取文本内容
    
    Args:
        pdf_path: PDF文件路径或二进制数据
        num_pages: 要加载的页数，None表示加载全部页面
        min_size: 最小文本大小，小于此值将抛出异常
        
    Returns:
        str: 提取的文本内容
    """
    print(f"开始加载文件: {pdf_path if isinstance(pdf_path, str) else '二进制数据'}")
    print(f"页数限制: {num_pages if num_pages else '无限制'}")
    
    # 检查pdf_path是否为bytes对象
    if isinstance(pdf_path, bytes):
        print("检测到二进制数据，将保存为临时文件")
        import tempfile
        try:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                temp_pdf.write(pdf_path)
                pdf_path = temp_pdf.name
                print(f"已将二进制数据保存为临时文件: {pdf_path}")
        except Exception as e:
            print(f"保存二进制数据到临时文件时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            raise Exception(f"保存二进制数据到临时文件时出错: {str(e)}")
    
    # 检查文件是否存在
    if isinstance(pdf_path, str) and not os.path.exists(pdf_path):
        error_msg = f"PDF文件不存在: {pdf_path}"
        print(error_msg)
        raise FileNotFoundError(error_msg)
    
    # 检查文件大小
    if isinstance(pdf_path, str):
        file_size = os.path.getsize(pdf_path)
        print(f"PDF文件大小: {file_size / 1024:.2f} KB")
        if file_size == 0:
            error_msg = f"PDF文件大小为0: {pdf_path}"
            print(error_msg)
            raise Exception(error_msg)
    
    # 检查文件头，确认是PDF文件
    try:
        with open(pdf_path, 'rb') as f:
            header = f.read(5)
            print(f"文件头: {header}")
            if header != b'%PDF-':
                error_msg = f"文件不是有效的PDF格式（文件头：{header}）: {pdf_path}"
                print(error_msg)
                raise Exception(error_msg)
    except Exception as e:
        print(f"检查文件头时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        raise Exception(f"检查文件头时出错: {str(e)}")
    
    # 尝试使用pymupdf4llm加载
    try:
        print("使用 pymupdf4llm 尝试加载文件...")
        start_time = time.time()
        
        try:
            # 检查pymupdf4llm版本
            try:
                print(f"检查pymupdf4llm版本: {pymupdf4llm.__version__ if hasattr(pymupdf4llm, '__version__') else '未知'}")
            except Exception as e:
                print(f"获取pymupdf4llm版本时出错: {str(e)}")
            
            if num_pages is None:
                print("尝试加载全文...")
                text = pymupdf4llm.to_markdown(pdf_path)
                print("pymupdf4llm.to_markdown调用成功，获取到文本")
            else:
                print(f"尝试加载前 {num_pages} 页...")
                reader = PdfReader(pdf_path)
                total_pages = len(reader.pages)
                print(f"PDF总页数: {total_pages}")
                min_pages = min(total_pages, num_pages)
                print(f"将加载 {min_pages} 页")
                text = pymupdf4llm.to_markdown(pdf_path, pages=list(range(min_pages)))
                print("pymupdf4llm.to_markdown调用成功，获取到文本")
        except Exception as e:
            print(f"pymupdf4llm加载PDF时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            raise Exception(f"pymupdf4llm加载PDF时出错: {str(e)}")
            
        end_time = time.time()
        duration = end_time - start_time
        
        text_length = len(text)
        word_count = len(text.split())
        print(f"pymupdf4llm 加载完成，耗时 {duration:.2f} 秒")
        print(f"提取文本长度: {text_length} 字符，约 {word_count} 个单词")
        
        if text_length < min_size:
            print(f"警告: 提取的文本太短 ({text_length} < {min_size})，将尝试其他方法")
            raise Exception(f"文本太短 ({text_length} < {min_size})")
            
        print("成功使用 pymupdf4llm 加载文件")
        return text
        
    except Exception as e:
        print(f"pymupdf4llm 加载失败: {str(e)}，尝试使用 pypdf")
        
        # 直接尝试使用pypdf加载，跳过pymupdf（因为可能未安装）
        try:
            print("使用 pypdf 尝试加载文件...")
            start_time = time.time()
            
            # 检查pypdf版本
            try:
                from pypdf import __version__ as pypdf_version
                print(f"pypdf版本: {pypdf_version}")
            except Exception as e:
                print(f"获取pypdf版本时出错: {str(e)}")
            
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages)
            print(f"PDF总页数: {total_pages}")
            
            text = ""
            if num_pages is None:
                print(f"将加载全部 {total_pages} 页")
                for i, page in enumerate(reader.pages):
                    if i % 10 == 0:
                        print(f"正在处理第 {i+1} 页...")
                    page_text = page.extract_text()
                    text += page_text + "\n"
                    print(f"第 {i+1} 页文本长度: {len(page_text)} 字符")
                    if i < 2:  # 只打印前两页的预览
                        print(f"第 {i+1} 页文本预览: {page_text[:100]}...")
            else:
                pages_to_load = min(total_pages, num_pages)
                print(f"将加载 {pages_to_load} 页")
                for i, page in enumerate(reader.pages[:pages_to_load]):
                    if i % 10 == 0:
                        print(f"正在处理第 {i+1} 页...")
                    page_text = page.extract_text()
                    text += page_text + "\n"
                    print(f"第 {i+1} 页文本长度: {len(page_text)} 字符")
                    if i < 2:  # 只打印前两页的预览
                        print(f"第 {i+1} 页文本预览: {page_text[:100]}...")
            
            end_time = time.time()
            duration = end_time - start_time
            
            text_length = len(text)
            word_count = len(text.split())
            print(f"pypdf 加载完成，耗时 {duration:.2f} 秒")
            print(f"提取文本长度: {text_length} 字符，约 {word_count} 个单词")
            
            if text_length < min_size:
                print(f"警告: 提取的文本太短 ({text_length} < {min_size})")
                if text_length > 0:
                    print(f"提取的文本预览: {text[:200]}...")
                else:
                    print("提取的文本为空")
                raise Exception(f"提取的文本太短 ({text_length} < {min_size})")
            
            print("成功使用 pypdf 加载文件")
            return text
            
        except Exception as e:
            print(f"所有PDF加载方法都失败: {str(e)}")
            traceback.print_exc()
            raise Exception(f"无法加载PDF文件: {str(e)}")

    return text


def load_review(path):
    with open(path, "r") as json_file:
        loaded = json.load(json_file)
    return loaded["review"]


# get directory of this file
dir_path = os.path.dirname(os.path.realpath(__file__))

fewshot_papers = [
    os.path.join(dir_path, "fewshot_examples/132_automated_relational.pdf"),
    os.path.join(dir_path, "fewshot_examples/attention.pdf"),
    os.path.join(dir_path, "fewshot_examples/2_carpe_diem.pdf"),
]

fewshot_reviews = [
    os.path.join(dir_path, "fewshot_examples/132_automated_relational.json"),
    os.path.join(dir_path, "fewshot_examples/attention.json"),
    os.path.join(dir_path, "fewshot_examples/2_carpe_diem.json"),
]


def get_review_fewshot_examples(num_fs_examples=1):
    fewshot_prompt = """
Below are some sample reviews, copied from previous machine learning conferences.
Note that while each review is formatted differently according to each reviewer's style, the reviews are well-structured and therefore easy to navigate.
"""
    for paper, review in zip(
        fewshot_papers[:num_fs_examples], fewshot_reviews[:num_fs_examples]
    ):
        txt_path = paper.replace(".pdf", ".txt")
        if os.path.exists(txt_path):
            with open(txt_path, "r") as f:
                paper_text = f.read()
        else:
            paper_text = load_paper(paper)
        review_text = load_review(review)
        fewshot_prompt += f"""
Paper:

```
{paper_text}
```

Review:

```
{review_text}
```
"""

    return fewshot_prompt


meta_reviewer_system_prompt = """你是中国国家自然科学基金委员会的资深评审专家。
你正在负责对一个已经由{reviewer_count}位评审专家评审过的国家自然科学基金项目进行综合评审。
你的任务是将这些评审意见整合成一个单一的综合评审意见，保持相同的格式。
请保持批判性和谨慎性，寻找共识，尊重所有评审专家的意见。
你的评审将直接影响项目是否获得资助，因此必须公正、客观、负责任。
请特别关注项目的创新性、科学价值、研究基础、研究方案可行性、研究条件、预期成果和申请经费合理性等方面。
在做出"熟悉程度"、"综合评价"和"资助意见"的判断时，应综合考虑各位评审专家的意见，给出合理的评价。"""


def get_meta_review(model, client, temperature, reviews, stream_handler=None):
    """
    生成元评审结果，整合多个评审意见
    
    Args:
        model: 使用的模型
        client: API客户端
        temperature: 温度参数
        reviews: 评审结果列表
        stream_handler: 流式处理函数
        
    Returns:
        dict: 元评审结果
    """
    # Write a meta-review from a set of individual reviews
    review_text = ""
    for i, r in enumerate(reviews):
        review_text += f"""
Review {i + 1}/{len(reviews)}:
```
{json.dumps(r, ensure_ascii=False, indent=2)}
```
"""
    base_prompt = nsfc_form + review_text

    try:
        print(f"[{time.strftime('%H:%M:%S')}] 开始生成元评审，整合{len(reviews)}个评审意见", file=sys.stderr)
        print(f"[{time.strftime('%H:%M:%S')}] 元评审提示词长度: {len(base_prompt)} 字符", file=sys.stderr)
        
        # 打印每个评审的关键信息
        for i, r in enumerate(reviews):
            print(f"[{time.strftime('%H:%M:%S')}] 评审 {i+1} 熟悉程度: {r.get('熟悉程度', 'N/A')}, 综合评价: {r.get('综合评价', 'N/A')}, 资助意见: {r.get('资助意见', 'N/A')}", file=sys.stderr)
        
        llm_review, msg_history = get_response_from_llm(
            base_prompt,
            model=model,
            client=client,
            system_message=meta_reviewer_system_prompt.format(reviewer_count=len(reviews)),
            msg_history=None,
            temperature=temperature,
            stream_handler=stream_handler  # 传递流式处理函数
        )
        
        print(f"[{time.strftime('%H:%M:%S')}] 元评审响应获取成功，长度: {len(llm_review)} 字符", file=sys.stderr)
        print(f"[{time.strftime('%H:%M:%S')}] 元评审响应预览: {llm_review[:200]}...", file=sys.stderr)
        
        # 如果有流式处理函数，传递完整响应
        if stream_handler:
            stream_handler(llm_review)
        
        meta_review = extract_json_between_markers(llm_review)
        
        if meta_review:
            print(f"[{time.strftime('%H:%M:%S')}] 元评审JSON解析成功", file=sys.stderr)
            print(f"[{time.strftime('%H:%M:%S')}] 元评审结果: 熟悉程度={meta_review.get('熟悉程度', 'N/A')}, 综合评价={meta_review.get('综合评价', 'N/A')}, 资助意见={meta_review.get('资助意见', 'N/A')}", file=sys.stderr)
        else:
            print(f"[{time.strftime('%H:%M:%S')}] 元评审JSON解析失败，将使用第一个评审结果", file=sys.stderr)
            
        return meta_review
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 元评审生成出错: {str(e)}", file=sys.stderr)
        print(f"[{time.strftime('%H:%M:%S')}] 将使用第一个评审结果作为备选", file=sys.stderr)
        return None
