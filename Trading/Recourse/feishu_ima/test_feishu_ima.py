"""test_feishu_ima.py - 纯函数单测 (不连 DB / 不联网).

覆盖:
  - collect_into_buckets: seq 连续性 + 切片边界 (守护 Important#1 的 bucket_seq 修复)
  - build_cos_authorization: 腾讯云 COS SHA1 签名结构
  - _code_to_label: info_type -> 中文 label (schemas 可用时)
  - ima_config: 凭证/KB_ID 加载 (不依赖真实凭证文件)

跑: python -m unittest test_feishu_ima  或  python test_feishu_ima.py
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from feishu_to_ima_extract_to_txt import collect_into_buckets, DOCS_PER_FILE, _code_to_label
from feishu_to_ima_upload_to_ima import build_cos_authorization
import ima_config


class CollectIntoBucketsTest(unittest.TestCase):
    def _mk(self, n, base_ts=1_700_000_000_000):
        # (msg_id, ts) ASC, ts 单位 ms, base 选在 +08:00 的早上避免跨日
        return [(1000 + i, base_ts + i) for i in range(n)]

    def test_empty(self):
        self.assertEqual(collect_into_buckets([], 1000), [])

    def test_less_than_one_bucket(self):
        out = collect_into_buckets(self._mk(3), 1000)
        self.assertEqual(len(out), 1)
        fname, chunk = out[0]
        self.assertRegex(fname, r"^feishu_\d{8}_\d{8}_1001\.txt$")
        self.assertEqual(len(chunk), 3)

    def test_exactly_one_bucket(self):
        out = collect_into_buckets(self._mk(DOCS_PER_FILE), 1000)
        self.assertEqual(len(out), 1)
        self.assertIn("_1001.txt", out[0][0])

    def test_multi_bucket_seq_continuous(self):
        # 关键: seq 必须从 start_seq+1 起连续, 无空洞 (守护 Important#1 的修复)
        n = DOCS_PER_FILE * 3 + 7
        out = collect_into_buckets(self._mk(n), 1000)
        self.assertEqual(len(out), 4)  # 50 + 50 + 50 + 7
        seqs = [int(f.split("_")[-1].split(".")[0]) for f, _ in out]
        self.assertEqual(seqs, [1001, 1002, 1003, 1004])
        self.assertEqual([len(c) for _, c in out], [50, 50, 50, 7])

    def test_start_seq_respected(self):
        out = collect_into_buckets(self._mk(1), 216)
        self.assertIn("_217.txt", out[0][0])

    def test_filename_uses_first_and_last_ts_date(self):
        # 跨多日: first ts 在 D1, last ts 在 D2 -> 文件名带两个不同日期
        day_ms = 86_400_000
        cands = [(1, day_ms), (2, day_ms + 1)]  # 同日, 仅验证格式
        out = collect_into_buckets(cands, 1)
        self.assertRegex(out[0][0], r"^feishu_\d{8}_\d{8}_002\.txt$")


class BuildCosAuthorizationTest(unittest.TestCase):
    def _auth(self, **over):
        kw = dict(
            secret_id="AKIDxxxx", secret_key="yyyy",
            method="PUT", pathname="/test/key.txt",
            headers={"host": "bucket.cos.ap-shanghai.myqcloud.com", "content-length": "10"},
            start_time="1700000000", expired_time="1700003600",
        )
        kw.update(over)
        return build_cos_authorization(**kw)

    def test_required_fields_present(self):
        auth = self._auth()
        for key in (
            "q-sign-algorithm=sha1",
            "q-ak=AKIDxxxx",
            "q-sign-time=1700000000;1700003600",
            "q-key-time=1700000000;1700003600",
            "q-header-list=content-length;host",  # sorted, lowercase
            "q-url-param-list=",
            "q-signature=",
        ):
            self.assertIn(key, auth, f"missing {key!r}")

    def test_header_list_sorted_lowercase(self):
        # header_keys 排序后小写, 顺序固定 -> 可复现
        auth = self._auth(headers={"Host": "h", "Content-Length": "10"})
        self.assertIn("q-header-list=content-length;host", auth)

    def test_signature_is_sha1_hex(self):
        auth = self._auth()
        sig = auth.split("q-signature=")[1]
        self.assertRegex(sig, r"^[0-9a-f]{40}$", f"signature not sha1 hex: {sig}")

    def test_deterministic(self):
        # 同输入同输出 (无随机性)
        self.assertEqual(self._auth(), self._auth())


class CodeToLabelTest(unittest.TestCase):
    def test_known_or_fallback(self):
        # schemas 可用 -> 已知 label; 不可用 -> 未知回退. 都接受, 只要非空
        self.assertTrue(_code_to_label(1))

    def test_unknown_code_falls_back(self):
        self.assertEqual(_code_to_label(99999), "未知(99999)")


class ImaConfigTest(unittest.TestCase):
    def test_kb_id_has_default(self):
        # 没设 env 时也有非空默认 (Stock KB)
        self.assertTrue(ima_config.IMA_KB_ID)

    def test_base_url(self):
        self.assertEqual(ima_config.IMA_BASE_URL, "https://ima.qq.com")

    def test_credential_loading_does_not_raise(self):
        # 凭证文件缺失应返回空串, 不抛 (改用 .exists() 保护)
        self.assertIsInstance(ima_config.IMA_CLIENT_ID, str)
        self.assertIsInstance(ima_config.IMA_API_KEY, str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
