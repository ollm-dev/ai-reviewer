import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.conf import get_conf
from app.controller.api import launch_app
from utils.log import get_logger
# 获取配置
conf = get_conf()
logger = get_logger("server.main")

if __name__ == '__main__':
    logger.info(f"启动服务，环境: {conf['env']}")
    launch_app(conf["server"]["host"], conf["server"]["port"])
