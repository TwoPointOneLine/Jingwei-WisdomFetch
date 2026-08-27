"""
应用基础设置配置（端口 / 应用名）。

对应 .env 中 IMPORT_APP_* / QUERY_APP_* / AUTH_APP_* 字段。
对外导出类名为 settings（文档约定）。
"""
from jingwei_common.config.common import env_int, env_str


class SettingsConfig:
    # 导入服务
    import_app_name: str = env_str("IMPORT_APP_NAME", "jingwei-import")
    import_app_port: int = env_int("IMPORT_APP_PORT", 8081)
    # 查询服务
    query_app_name: str = env_str("QUERY_APP_NAME", "jingwei-query")
    query_app_port: int = env_int("QUERY_APP_PORT", 8082)
    # 认证服务
    auth_app_name: str = env_str("AUTH_APP_NAME", "jingwei-auth")
    auth_app_port: int = env_int("AUTH_APP_PORT", 8083)
    # 用户服务
    user_app_name: str = env_str("USER_APP_NAME", "jingwei-user")
    user_app_port: int = env_int("USER_APP_PORT", 8084)
    # 网关服务
    gateway_app_name: str = env_str("GATEWAY_APP_NAME", "jingwei-gateway")
    gateway_app_port: int = env_int("GATEWAY_APP_PORT", 8080)
    # 网关鉴权模式：strict=必须 token / optional=带 token 则校验（默认）
    gateway_auth_mode: str = env_str("GATEWAY_AUTH_MODE", "optional")
    # 网关限流：每分钟每 IP 最大请求数（0=关闭）
    gateway_rate_limit: int = env_int("GATEWAY_RATE_LIMIT", 0)
    # 服务通用
    app_host: str = env_str("APP_HOST", "0.0.0.0")
    cors_origins: str = env_str("CORS_ORIGINS", "*")


settings = SettingsConfig()
