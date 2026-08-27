"""分层候选生成编排单测（P0）：历史→规则→语义→LLM 覆盖路径。

不连真实 DB：monkeypatch db + 各层函数，验证编排层的分层顺序、
早停、REJECTED 过滤与 stats 统计。真实 LLM 链路不在此处测。
```
python -m pytest tests/test_binding_matcher_layered.py -q
or python -m unittest tests.test_binding_matcher_layered -v
```
"""
from __future__ import annotations

import unittest
from unittest import mock

from app.binding import candidate as cand
import app.binding.matcher as m


class EO:
    def __init__(self, eid, block="B1", layer="L-DATA"):
        self.id = eid
        self.block_name = block
        self.layer_name = layer
        self.project_id = 1


_BOQ = [{"code": "A-01"}, {"code": "B-02"}]


class _Recorder:
    """记录 create_binding_candidate 调用"""

    def __init__(self):
        self.calls = []
        self.ids = 0

    def __call__(self, project_id, eo_id, boq_id, **kw):
        self.ids += 1
        self.calls.append({"eo": eo_id, "boq": boq_id, **kw})
        return self.ids


def _make(match_rule=(), hist=(), semantic=(), rejected=(), llm_out=None,
          bound=frozenset(), eos=None, boq=None, fallback=()):
    """构造分层编排的假环境，返回 (fakes, recorder)。"""
    rec = _Recorder()
    dbm = mock.MagicMock()
    eos = list(eos if eos is not None else [EO(1)])
    dbm.get_engineering_objects.return_value = eos
    dbm.get_boq_items.return_value = list(boq if boq is not None else list(_BOQ))
    dbm.create_binding_candidate.side_effect = rec

    fakes = dict(
        db=dbm,
        already_bound=lambda eo: eo.id in bound,
        _rejected_pairs=mock.MagicMock(side_effect=lambda pid, eo: set(rejected)),
        historical_confirmed=mock.MagicMock(side_effect=lambda pid, eo: list(hist)),
        match_rule=mock.MagicMock(side_effect=lambda pid, eo, items=None: list(match_rule)),
        semantic_candidates=mock.MagicMock(side_effect=lambda pid, eo: list(semantic)),
        _boq_top_n_for_llm=mock.MagicMock(side_effect=lambda pid, eo, top_n=None: list(fallback)),
    )
    if llm_out is not None:
        fakes["llm_rerank"] = mock.MagicMock(
            side_effect=lambda pid, eo, base, top_n=None, items=None: list(llm_out))
    return fakes, rec


def _generate(fakes, use_llm=False, **kw):
    with mock.patch.multiple(m, **fakes):
        return m.generate_candidates(1, use_llm=use_llm, **kw)


class BindingLayeredTest(unittest.TestCase):
    def test_hist_hit_stops_early(self):
        """第1层历史确认命中 → 只写 RULE(1.0)，规则/语义/LLM 都不跑"""
        fakes, rec = _make(hist=[(10, "昨日确认")])
        res = _generate(fakes)
        self.assertEqual(res["candidates"], 1)
        self.assertEqual(rec.calls[0]["boq"], 10)
        self.assertEqual(rec.calls[0]["method"], cand.METHOD_RULE)
        self.assertEqual(rec.calls[0]["score"], 1.0)
        self.assertEqual(fakes["match_rule"].call_count, 0)
        self.assertEqual(res["stats"]["rule"], 1)

    def test_rule_strong_skips_semantic_and_llm(self):
        """规则强命中（score≥RULE_STRONG_MIN）→ 只写 RULE，不跑语义/LLM"""
        fakes, rec = _make(match_rule=[(10, 0.9, "规则强")])
        res = _generate(fakes, use_llm=True)
        self.assertEqual(res["candidates"], 1)
        self.assertEqual(rec.calls[0]["score"], 0.9)
        self.assertEqual(rec.calls[0]["method"], cand.METHOD_RULE)
        self.assertEqual(fakes["semantic_candidates"].call_count, 0)
        self.assertNotIn("llm_rerank", fakes)  # 强规则路径根本不设置 LLM 层
        self.assertEqual(res["stats"]["rule"], 1)

    def test_weak_rule_plus_semantic_no_llm(self):
        """弱规则 + 语义 → 合并写入（use_llm=False）"""
        fakes, rec = _make(match_rule=[(10, 0.4, "弱")], semantic=[(11, 0.6, "语义")])
        res = _generate(fakes)
        self.assertEqual({c["boq"] for c in rec.calls}, {10, 11})
        self.assertEqual(res["stats"]["embedding"], 1)

    def test_llm_rerank_on_union(self):
        """LLM 精排在 规则+语义 并集上重排，LLM 选中项置顶"""
        llm_out = [(12, 0.9, "LLM选", cand.METHOD_LLM, 7),
                   (10, 0.4, "弱规则", cand.METHOD_RULE, None)]
        fakes, rec = _make(match_rule=[(10, 0.4, "弱规则")],
                           semantic=[(11, 0.6, "语义")], llm_out=llm_out)
        res = _generate(fakes, use_llm=True)
        self.assertEqual(res["stats"]["llm"], 1)
        # LLM 在并集内重排后替换候选集：只写 LLM 选中 + base 保底，未选中的语义项不再写
        written = {c["boq"] for c in rec.calls}
        self.assertEqual(written, {12, 10})
        self.assertEqual(rec.calls[0]["boq"], 12)  # LLM 选中置顶

    def test_no_match_all_layers_empty(self):
        """全部层级均无产出（清洗 fallback 也空）→ no_match，无候选写入"""
        fakes, rec = _make()
        res = _generate(fakes)
        self.assertEqual(res["candidates"], 0)
        self.assertEqual(res["stats"]["no_match"], 1)
        self.assertEqual(rec.calls, [])

    def test_no_match_when_fallback_empty(self):
        """规则/语义空 + fallback 空 → no_match；fallback 非空 → 写 EMBEDDING 候选"""
        # fallback 空
        fakes, rec = _make(fallback=[])
        res = _generate(fakes, use_llm=True)
        self.assertEqual(res["stats"]["no_match"], 1)
        # fallback 非空（无 LLM：截断 top_n 写入）
        fakes2, rec2 = _make(fallback=[(20, 0.4, "交集", cand.METHOD_EMBEDDING, None)])
        res2 = _generate(fakes2)
        self.assertEqual({c["boq"] for c in rec2.calls}, {20})
        self.assertEqual(res2["stats"]["embedding"], 1)

    def test_rejected_filtered_all_layers(self):
        """REJECTED 组合在各层都不再写入（弱规则不短路 → 语义补上未拒项）"""
        fakes, rec = _make(match_rule=[(10, 0.5, "规则"), (12, 0.4, "规则")],
                         semantic=[(11, 0.6, "语义"), (13, 0.5, "语义")],
                         hist=[(10, "历史")], rejected={10, 11})
        res = _generate(fakes)
        written = {c["boq"] for c in rec.calls}
        self.assertEqual(written, {12, 13})
        self.assertEqual(res["stats"]["skipped_rejected"], 2)

    def test_bound_skipped(self):
        fakes, rec = _make(bound={1})
        res = _generate(fakes)
        self.assertEqual(res["stats"]["skipped_bound"], 1)
        self.assertEqual(rec.calls, [])

    def test_llm_no_match_rejects(self):
        """LLM 判定 no_match → 该 EO 不写候选，计入 no_match（而非 rule/llm）"""
        fakes, rec = _make(match_rule=[(10, 0.4, "弱规则")],
                           semantic=[(11, 0.6, "语义")], llm_out=[])
        res = _generate(fakes, use_llm=True)
        self.assertEqual(rec.calls, [])
        self.assertEqual(res["stats"]["no_match"], 1)
        self.assertEqual(res["stats"]["llm"], 0)

    def test_llm_batch_multiple_eos_backfill(self):
        """P2-2：多 EO 并发进 LLM 层，各自重排结果回填且全部落库"""
        eos = [EO(1), EO(2, block="B2", layer="L-DATA")]
        fakes, rec = _make(eos=eos, match_rule=[(10, 0.4, "弱规则")],
                           llm_out=[(12, 0.9, "LLM选", cand.METHOD_LLM, 7),
                                    (10, 0.4, "弱规则", cand.METHOD_RULE, None)])
        res = _generate(fakes, use_llm=True)
        self.assertEqual(res["stats"]["llm"], 2)          # 两个 EO 都走 LLM 层
        self.assertEqual({c["boq"] for c in rec.calls}, {12, 10})
        self.assertEqual(fakes["llm_rerank"].call_count, 2)
        # 并发调用携带预载 BOQ（P2-2：避免每作业重复查表）
        _, kw = fakes["llm_rerank"].call_args_list[0]
        self.assertIn("items", kw)


if __name__ == "__main__":
    unittest.main()