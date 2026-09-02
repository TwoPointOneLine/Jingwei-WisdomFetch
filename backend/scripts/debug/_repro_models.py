"""临时复现脚本：验证两个本地模型（BGE-M3 向量 / BGE-Reranker 重排序）当前是否可用。"""
import os
import sys
import traceback

os.environ.setdefault("BGE_M3", "local")  # 确保走 local 后端
os.environ.setdefault("BGE_M3_PATH", r"D:\ai_models\modelscope_cache\models\BAAI\bge-m3")
os.environ.setdefault("BGE_RERANKER_LARGE", r"D:\ai_models\modelscope_cache\models\BAAI\bge-reranker-v2-m3")
os.environ.setdefault("BGE_DEVICE", "cuda")
os.environ.setdefault("BGE_REARNKER_DEVICE", "cuda")

print("STEP 1: import jingwei_common.ai (触发兼容 shim + FlagEmbedding import)", flush=True)
try:
    from jingwei_common.ai import BGEM3Embedder, BGEReranker
    print("  import OK", flush=True)
except Exception:
    traceback.print_exc()
    sys.exit(1)

print("STEP 2: 加载 BGE-M3 并产出混合向量", flush=True)
try:
    out = BGEM3Embedder.embed_documents(["精卫填海，衔石以填沧海。", "金融知识库提供合规问答。"])
    dense = out["dense"]
    sparse = out["sparse"]
    print(f"  dense dims={len(dense)} x {len(dense[0])}", flush=True)
    print(f"  sparse[0] terms={len(sparse[0])}, sparse[1] terms={len(sparse[1])}", flush=True)
    q = BGEM3Embedder.embed_query("如何查询产品风险等级?")
    print(f"  query dense dims={len(q['dense'][0])}, sparse terms={len(q['sparse'][0])}", flush=True)
    print("  BGE-M3 OK", flush=True)
    # 释放 BGE-M3 显存，避免与 Reranker 同时驻留 8GB 显存导致 OOM
    BGEM3Embedder._model = None
    import torch as _torch
    if _torch.cuda.is_available():
        _torch.cuda.empty_cache()
except Exception:
    traceback.print_exc()
    sys.exit(2)

print("STEP 3: 加载 BGE-Reranker 并打分", flush=True)
try:
    score = BGEReranker.compute_score(
        [["如何查询产品风险等级?", "该产品的风险等级为 R3，中等风险。"],
         ["如何查询产品风险等级?", "今天天气晴朗，适合出游。"]]
    )
    print(f"  reranker scores={score}", flush=True)
    print("  BGE-Reranker OK", flush=True)
except Exception:
    traceback.print_exc()
    sys.exit(3)

print("ALL MODELS OK", flush=True)
