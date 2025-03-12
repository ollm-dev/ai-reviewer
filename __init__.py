import os
import sys

# 设置默认编码为 UTF-8
if sys.platform.startswith('win'):
    # 在 Windows 环境下设置默认编码
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)
