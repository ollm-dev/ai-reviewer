import os
import sys

# 将项目根目录添加到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

import gradio as gr

from util.conf import get_conf
from app.reviewer import review_tab

conf = get_conf()

# Gradio 界面
with gr.Blocks(theme=gr.themes.Soft(
    primary_hue="blue",
    secondary_hue="sky", 
    neutral_hue="slate",
    font=["Source Sans Pro", "ui-sans-serif", "system-ui"]
)) as app:
    review_tab()


if __name__ == '__main__':
    s_conf = conf["server"]
    app.launch(server_name=s_conf["host"], server_port=s_conf["port"])
