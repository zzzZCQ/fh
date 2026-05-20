"""应用配置文件"""
import os

# 基础路径
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """基础配置"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'delivery-notification-secret-key')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///delivery.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 静态文件缓存（秒）
    SEND_FILE_MAX_AGE_DEFAULT = 3600


# 顺丰API配置
SF_APP_ID = os.environ.get('SF_APP_ID', 'YF40LPM6')
SF_APP_SECRET = os.environ.get('SF_APP_SECRET', '6E6DhfBPH30SQevLCS0N9FFgwG5OzzXM')
SF_API_URL = os.environ.get('SF_API_URL', 'https://bspgw.sf-express.com/std/service')
SF_SERVICE_CODE = 'EXP_RECE_SEARCH_ROUTES'

# 钉钉企业应用配置
DINGTALK_CORP_ID = os.environ.get('DINGTALK_CORP_ID', 'ding1003c109e5102cc3f2c783f7214b6d69')
DINGTALK_APP_KEY = os.environ.get('DINGTALK_APP_KEY', 'ding9qltojyt3seunjta')
DINGTALK_APP_SECRET = os.environ.get('DINGTALK_APP_SECRET', 'yweAXcdsizcG-P45KbKjLOzEqbH0-IbqNSrC0mSDg9v1rkZn-ovMyibSfQszmYga')
DINGTALK_AGENT_ID = os.environ.get('DINGTALK_AGENT_ID', '4577186143')
DINGTALK_CHAT_ID = os.environ.get('DINGTALK_CHAT_ID', '168165024534')
DINGTALK_ROBOT_CODE = os.environ.get('DINGTALK_ROBOT_CODE', '')
DINGTALK_OPEN_CONVERSATION_ID = os.environ.get('DINGTALK_OPEN_CONVERSATION_ID', 'cid8zaRxCQEQJSyp/y0tGojbQ==')

# 钉钉文件预览/在线文档配置
DINGTALK_UNION_ID = os.environ.get('DINGTALK_UNION_ID', '9rFTCVNciSNLf5BjDXxlRogiEiE')
DINGTALK_SPACE_ID = os.environ.get('DINGTALK_SPACE_ID', '28850517739')
DINGTALK_OPERATOR_ID = os.environ.get('DINGTALK_OPERATOR_ID', '9rFTCVNciSNLf5BjDXxlRogiEiE')
DINGTALK_WORKSPACE_ID = os.environ.get('DINGTALK_WORKSPACE_ID', 'Jpaq7SGr4jAWDP0x')

# 钉钉部门ID（用于设置文档权限，钉钉API不支持群组，只能设置部门权限）
# 在钉钉管理后台 -> 组织架构 -> 部门 -> 点击部门查看部门ID
# 根部门ID通常是1，表示全员可见
DINGTALK_DEPT_ID = os.environ.get('DINGTALK_DEPT_ID', '1')
