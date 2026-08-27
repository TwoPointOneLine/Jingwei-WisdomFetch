"""配置层测试：环境读取工具与配置单例。"""
from jingwei_common.config import infra_config, lm_config, settings
from jingwei_common.config.common import env_bool, env_int, env_str


def test_env_str_default():
    assert env_str("JINGWEI_UNKNOWN_KEY_XYZ") == ""
    assert env_str("JINGWEI_UNKNOWN_KEY_XYZ", "abc") == "abc"


def test_env_bool_default():
    assert env_bool("JINGWEI_UNKNOWN_KEY_XYZ") is False
    assert env_bool("JINGWEI_UNKNOWN_KEY_XYZ", True) is True


def test_env_int_default():
    assert env_int("JINGWEI_UNKNOWN_KEY_XYZ") == 0
    assert env_int("JINGWEI_UNKNOWN_KEY_XYZ", 8081) == 8081


def test_config_singletons():
    assert settings.import_app_port == 8081
    assert settings.query_app_port == 8082
    assert settings.auth_app_port == 8083
    assert lm_config.provider in {"dashscope", "local"}
    assert infra_config.app is settings
    assert infra_config.llm is lm_config


def test_lm_config_switch():
    origin = lm_config.provider
    try:
        lm_config.provider = "local"
        assert lm_config.is_local is True
        assert lm_config.active_default_model == lm_config.local_default_model
        lm_config.provider = "dashscope"
        assert lm_config.is_local is False
    finally:
        lm_config.provider = origin
