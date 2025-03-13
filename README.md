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
  * 在review_pape向perform_review传入提示词：开始生成评审意见...
* perform_review 通过 get_response_from_llm 调用AI接口
  * perform_review函数功能是：输出评审与反思的日志
* 结果返回并显示在 review_output 组件中
* 进度信息显示在 progress_output 组件中



# prompt 改写

# backgroud

- 项目前端基于Gradio , 后端python调用各种函数 ， 函数调用关系参考readme.md

# task

- 现在后端输出使用日志（封装了函数：update_progress / print），但是我现在要在前端页面（我会给你一张前端图片，红色字体指明perform_review中log的展现位置）呈现出log中的内容
- 并且输出是流式的 ， 所以ai的输出可能要支持流式 ， 前端 app/reviwer.py 前端的也要支持流式
  - 你可能要在app/reviwer.py调用perform_review在【AI评审过程组件中】流式展示 ， 这个建议你要思考一下 ， 我不知到是否可行
- 时间很充足 ， 慢慢来 ， 你必须充分理解我提供的代码和图片 ，但是包括但限于我提供的

# tips

- 基于gradio
- 一定要实现流式输出
- 实现前端流式输出【AI评审、反思过程】
- 保证代码完整性 ， 若有没有完成的需要注明 ，下次在生成
- 用python方式注释
