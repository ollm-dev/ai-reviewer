# AI Reviewer

## Getting started

```shell
export no_proxy="localhost, 127.0.0.1, ::1"

ENV=prod python -m server.main
```

## Deploy

```shell
ssh root@180.76.103.165 -p 6600

tmux attach -t reviewer-api

cd /root/project/ai-reviewer

git pull

conda activate py311

# 如果有依赖更新
pip install -r requirements.txt -i https://pypi.mirrors.ustc.edu.cn/simple

# 记得确认 conf/default.prod.yaml 里面的配置
ENV=prod python -m server.main
```
