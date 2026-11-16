"""
fufu新闻 - 核心配置
=====================
应用全局配置管理，使用 pydantic-settings 从环境变量/.env 文件加载配置。
所有配置项通过 settings 单例全局访问。
"""
from pathlib import Path

from pydantic_settings import BaseSettings

# 项目根目录：fufu-server/app/core/config.py → 向上 4 级到达项目根
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
# 数据目录：存放 SQLite 数据库文件等
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """
    应用配置类——所有配置项均支持通过环境变量或 .env 文件覆盖。

    配置项说明：
    - app_name: 应用名称（显示在 Swagger/OpenAPI 文档标题中）
    - app_version: 应用版本号
    - database_url: SQLite 数据库连接字符串（使用 aiosqlite 异步驱动）
    - secret_key: JWT 签名密钥（生产环境务必更换为随机字符串）
    - access_token_expire_minutes: JWT 访问令牌过期时间（默认 7 天 = 10080 分钟）
    - default_username / default_password: 数据库初始化时创建的默认用户凭证
    - ai_backend: AI 后端标识（如 deepseek / openai / ollama）
    - ai_base_url: AI API 的完整请求地址
    - ai_model: AI 模型名称
    - ai_api_key: AI API 密钥
    - ai_temperature: AI 生成温度（0.0-1.0，越低越确定）
    - ai_auto_summary: 是否自动为文章生成 AI 摘要
    - ai_auto_tag: 是否自动为文章生成 AI 标签
    - newsapi_key: NewsAPI.org 的 API Key（可选，用于全网新闻搜索）
    """
    # 应用基本信息
    app_name: str = "fufu新闻"
    app_version: str = "1.0.0"

    # 数据库配置
    # 使用 as_posix() 统一为正斜杠，避免 Windows 反斜杠在 URL 中被转义
    database_url: str = f"sqlite+aiosqlite:///{(DATA_DIR / 'fufu.db').as_posix()}"

    # 安全配置
    secret_key: str = "fufu-news-secret-key-change-in-production"  # 生产环境务必修改
    access_token_expire_minutes: int = 10080  # JWT 过期时间（分钟），默认 7 天

    # 默认用户配置（首次启动时自动创建）
    default_username: str = "fufu"
    default_password: str = "fufu123"

    # AI 服务配置
    ai_backend: str = "deepseek"  # AI 后端标识
    ai_base_url: str = "https://api.deepseek.com/v1/chat/completions"  # AI API 地址
    ai_model: str = "deepseek-v4-pro"  # 使用的模型名称
    ai_api_key: str = ""  # API 密钥（请在 .env 中配置 AI_API_KEY）
    ai_temperature: float = 0.3  # 生成温度，较低的值为更确定性的输出
    ai_auto_summary: bool = True  # 抓取后自动生成摘要
    ai_auto_tag: bool = True  # 抓取后自动生成标签

    # NewsAPI 配置（可选，用于第三方新闻源）
    newsapi_key: str = ""  # NewsAPI.org key（免费 tier: https://newsapi.org/register）

    # 代理配置（用于访问境外 RSS 源）
    http_proxy: str = ""   # HTTP 代理地址，如 http://127.0.0.1:7890
    https_proxy: str = ""  # HTTPS 代理地址，如 http://127.0.0.1:7890

    # 频率限制配置
    rate_limit_enabled: bool = True          # 是否启用 API 频率限制
    rate_limit_requests_per_minute: int = 60 # 每 IP 每分钟最大请求数
    rate_limit_burst_size: int = 10          # 突发流量允许的额外请求数
    rate_limit_whitelist: str = "127.0.0.1,localhost,::1"  # 白名单 IP（逗号分隔）

    # 反爬虫配置
    anti_crawl_enabled: bool = True          # 是否启用反爬虫检测
    anti_crawl_block_duration_hours: int = 24  # 封禁时长（小时）

    # CORS 配置（不再使用 allow_origins=["*"] + credentials 的错误组合）
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )

    # AI 自定义 base_url 的域名白名单（SSRF 防护 + 防止服务端 Key 外泄）
    # 支持精确域名或 *.example.com 后缀匹配
    ai_allowed_hosts: str = (
        "api.deepseek.com,api.openai.com,api.moonshot.cn,"
        "open.bigmodel.cn,dashscope.aliyuncs.com,localhost,127.0.0.1"
    )

    # 未捕获异常是否把摘要回传给前端（生产建议 False）
    expose_error_detail: bool = True

    # 是否由后端托管已构建的前端产物（需先 npm run build）。
    # 默认 False：开发态前端由 Vite 独立运行在 3000，避免误挂载过期的 dist。
    serve_static: bool = False

    # 后端监听端口（供 python -m app.main 直启时使用，与 vite proxy / launch.py 保持一致）
    server_port: int = 8800

    @property
    def cors_origins_list(self) -> list[str]:
        """把逗号分隔的 CORS 配置解析成列表。"""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ai_allowed_hosts_list(self) -> list[str]:
        """把逗号分隔的 AI 域名白名单解析成列表。"""
        return [h.strip() for h in self.ai_allowed_hosts.split(",") if h.strip()]

    @property
    def using_default_secret(self) -> bool:
        """是否仍在使用默认/示例 JWT 密钥（仅用于启动告警，不改变行为）。"""
        weak = {
            "fufu-news-secret-key-change-in-production",
            "change-me-to-a-random-string",
        }
        return self.secret_key in weak

    class Config:
        """
        Pydantic 配置——指定从 .env 文件读取环境变量。

        注意：env_file 使用绝对路径，避免在非 fufu-server 目录下启动时加载不到 .env。
        """
        env_file = str(Path(__file__).resolve().parent.parent.parent / ".env")
        env_file_encoding = "utf-8"  # 文件编码


# 全局配置单例——在应用任何地方 import 即可使用
settings = Settings()
