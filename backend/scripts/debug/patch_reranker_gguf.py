"""外科手术式：原 bge-reranker-v2-m3 GGUF 完全不动，仅在 KV 段追加两条元数据
(general.task=rerank 与 bert.pooling_type=rank)，让 Ollama 识别为 reranker 类型。

保持所有张量字节原样，仅更新 kv_count 并在张量数据前补对齐填充，确保 Ollama 可解析。
"""
import struct
import hashlib
import gguf

ORIG = r"D:/Program/Config/Ollama/models/blobs/sha256-4bf51534d8d1aebced4de6eca4a8a39bd207170b42e3dcffa7718d194771a713"
OUT = r"D:/tmp/bge-reranker-v2-m3-rerank.gguf"
ALIGN = int(getattr(gguf.GGUFReader(ORIG, 'r'), 'alignment', 32))

with open(ORIG, 'rb') as f:
    data = f.read()

assert data[0:4] == b'GGUF', "not a GGUF"
version = struct.unpack('<I', data[4:8])[0]
tensor_count, kv_count = struct.unpack('<QQ', data[8:24])
assert version in (2, 3), f"unsupported version {version}"

r = gguf.GGUFReader(ORIG, 'r')
data_offset = int(r.data_offset)

# 真实 KV 字段（排除 GGUF.* 虚拟字段），按 offset 排序
real = sorted(
    [f for f in r.fields.values() if not f.name.startswith('GGUF.')],
    key=lambda f: int(f.offset),
)
kv_parts = []
for f in real:
    flen = sum(int(p.nbytes) for p in f.parts)
    kv_parts.append(data[int(f.offset): int(f.offset) + flen])
original_kv = b''.join(kv_parts)
# 校验：KV 段长度应等于 kv_end - 24
kv_end = int(real[-1].offset) + sum(int(p.nbytes) for p in real[-1].parts)
assert len(original_kv) == kv_end - 24, f"KV 长度不符: {len(original_kv)} vs {kv_end-24}"
assert data_offset % ALIGN == 0, "原 data_offset 未对齐"

STRING = int(gguf.GGUFValueType.STRING)
UINT32 = int(gguf.GGUFValueType.UINT32)


def make_entry(key: bytes, val: bytes) -> bytes:
    return (
        struct.pack('<Q', len(key))
        + key
        + struct.pack('<I', STRING)
        + struct.pack('<Q', len(val))
        + val
    )


# 条目1: general.task = "rerank"
entry1 = make_entry(b"general.task", b"rerank")
# 条目2: bert.pooling_type = 4 (GGUF_POOLING_TYPE_RANK，Ollama 判定 reranker 的标志)
#         该字段在 GGUF 规范里是整数枚举，不能写字符串，否则 llama-quantize 校验失败。
entry2 = struct.pack('<Q', len(b"bert.pooling_type")) + b"bert.pooling_type" + struct.pack('<I', UINT32) + struct.pack('<I', 4)

# KV 段整体增长 entry1+entry2，需让张量数据起点仍对齐到 ALIGN
total_extra = len(entry1) + len(entry2)
pad = (ALIGN - (total_extra % ALIGN)) % ALIGN

rest = data[kv_end:]
ti_len = data_offset - kv_end  # 张量信息段（在 KV 与张量数据之间）
new_rest = rest[:ti_len] + b'\x00' * pad + rest[ti_len:]

new_kv = original_kv + entry1 + entry2
new_header = data[0:4] + struct.pack('<I', version) + struct.pack('<QQ', tensor_count, kv_count + 2)

with open(OUT, 'wb') as f:
    f.write(new_header)
    f.write(new_kv)
    f.write(new_rest)

new_data_start = len(new_header) + len(new_kv) + ti_len + pad

# ---- 校验 ----
assert new_data_start % ALIGN == 0, f"张量数据起点未对齐: {new_data_start}"
# 张量数据区域字节必须与原文件完全一致
orig_tensor = data[data_offset:]
new_tensor = new_rest[ti_len + pad:]
assert hashlib.sha256(orig_tensor).hexdigest() == hashlib.sha256(new_tensor).hexdigest(), \
    "张量数据被改动！"
assert len(new_tensor) == len(orig_tensor), "张量数据长度变化"

print(f"ALIGN={ALIGN} entry1_len={len(entry1)} entry2_len={len(entry2)} pad={pad}")
print(f"new tensor-data start = {new_data_start}, aligned={new_data_start % ALIGN == 0}")
print(f"WROTE {OUT} ({len(new_header)+len(new_kv)+len(new_rest)} bytes)")
print(f"tensor bytes unchanged: sha256 match = {hashlib.sha256(orig_tensor).hexdigest()[:16]}...")

# 回读新文件确认两条元数据都在
v = gguf.GGUFReader(OUT, 'r')
print("verify general.task   =>", v.fields.get("general.task").contents())
print("verify bert.pooling_type =>", v.fields.get("bert.pooling_type").contents())
print("verify tensor count   =>", len(v.tensors))
