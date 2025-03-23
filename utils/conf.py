import os

from ruamel.yaml import YAML

from utils.log import get_logger

env = os.getenv("ENV", "dev")
yaml = YAML()
logger = get_logger("utils.conf")

# 项目根目录路径
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def read_yaml(yaml_path: str) -> dict:
    with open(yaml_path, "r") as f_yaml:
        datas = yaml.load(f_yaml)
    return datas


def get_conf() -> dict:
    if env == "dev":
        conf_path = os.path.join(ROOT_DIR, "conf", "default.yaml")
    else:
        conf_path = os.path.join(ROOT_DIR, "conf", f"default.{env}.yaml")
    conf_data = read_yaml(conf_path)
    conf_data["env"] = env
    return conf_data
