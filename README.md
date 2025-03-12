# AI Reviewer

这是一个典型的Gradio全栈应用，它通过Gradio框架优雅地将前端UI和后端处理逻辑整合在一起，实现了一个完整的论文评审系统。

* 前端：使用Gradio框架构建UI，提供文件上传、按钮交互和结果显示等功能
* 后端：包含PDF处理、AI模型调用和结果处理等核心逻辑
* 交互：通过Gradio的事件系统实现前后端通信，支持异步处理和进度显示
* 部署：使用Gradio内置的Web服务器提供HTTP服务

# Getting started

```shell
export no_proxy="localhost, 127.0.0.1, ::1"

ENV=prod python -m server.main
```

# UI组件

* PDF文件上传控件
* "开始评审"按钮
* 进度显示区域
* 评审结果显示区域
* "复制结果"按钮

# 文件调用逻辑

* 用户上传PDF文件 → pdf_input 组件
* 点击"开始评审" → 触发 review_wrapper 函数
* review_wrapper 调用 review_paper
* review_paper 调用 perform_review
* perform_review 通过 get_response_from_llm 调用AI接口
* 结果返回并显示在 review_output 组件中
* 进度信息显示在 progress_output 组件中
