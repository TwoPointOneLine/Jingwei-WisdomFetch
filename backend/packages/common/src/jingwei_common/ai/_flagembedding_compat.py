"""FlagEmbedding 与 transformers 版本兼容 shim。

处理两处已知的版本错配（FlagEmbedding 1.3.5 元数据要求 transformers>=4.44.2，
但该版本 tokenizer 已移除 `return_colbert` 参数，而 FlagEmbedding 仍会透传）：

1. FlagEmbedding 的 reranker 子模块在 transformers>=5 下因缺失
   `is_torch_fx_available` 而无法 import（5.x 已移除该符号）——补一个 shim。
2. FlagEmbedding 向 tokenizer 透传 `return_colbert`，transformers>=4.44.2 的
   tokenizer 不再接受该参数——给 batch_encode_plus/_batch_encode_plus/__call__
   打补丁，静默忽略 `return_colbert`（BGE-M3 的稀疏向量由模型计算，不依赖此参数）。
"""
from __future__ import annotations


def _patch_tokenizer_return_colbert() -> None:
    """让 transformers tokenizer 静默忽略 FlagEmbedding 透传的 return_colbert 参数。

    FlagEmbedding 的 M3Embedder 在调用 tokenizer 的 __call__ / pad 时都会透传
    return_colbert，而 transformers>=4.44.2 的 tokenizer 已移除该参数，故对这两个
    入口打补丁，在转发前弹出该关键字参数（BGE-M3 稀疏向量由模型计算，不依赖它）。
    """
    try:
        from transformers.tokenization_utils_base import PreTrainedTokenizerBase
    except Exception:  # pragma: no cover - 依赖未装时跳过
        return

    for _method in ("__call__", "pad", "batch_encode_plus", "_batch_encode_plus", "encode_plus"):
        _orig = getattr(PreTrainedTokenizerBase, _method, None)
        if _orig is None or getattr(_orig, "_jwf_patched", False):
            continue

        def _make_wrapper(orig):
            def _wrapper(self, *args, **kwargs):
                kwargs.pop("return_colbert", None)
                return orig(self, *args, **kwargs)

            _wrapper._jwf_patched = True
            return _wrapper

        setattr(PreTrainedTokenizerBase, _method, _make_wrapper(_orig))


def ensure_flagembedding_importable() -> None:
    """安装 FlagEmbedding 与 transformers>=4.44.2 的兼容补丁。

    幂等：重复调用安全。
    """
    # 1) 补 is_torch_fx_available（transformers>=5 缺失）
    try:
        from transformers.utils.import_utils import is_torch_fx_available  # noqa: F401
    except ImportError:
        import transformers.utils.import_utils as _iu

        if not hasattr(_iu, "is_torch_fx_available"):
            _iu.is_torch_fx_available = getattr(
                _iu, "is_torch_available", lambda: True
            )

    # 2) 让 tokenizer 忽略 FlagEmbedding 透传的 return_colbert
    _patch_tokenizer_return_colbert()
