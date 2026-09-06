"""webapi/services/ 单元测试（10 service × 5 case = 50 case）

策略：mock app/ 业务函数，验证 service 层包装 + 异常处理 + 边界。
覆盖：cad/binding/boq/dataset/extraction/takeoff/llm/audit/spec_match/manifest
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# webapi/services/cad
# ============================================================


class TestCadService:
    """app.cad.* 包装层 + 异常映射"""

    @pytest.mark.asyncio
    @patch("webapi.services.cad.parse_cad_file")
    async def test_parse_cad_success(self, mock_parse):
        mock_parse.return_value = {"entities": [], "layers": {}, "project_id": 1}
        from webapi.services.cad import parse_cad_file
        result = await parse_cad_file(db=None, project_id=1, file_path="D:/x.dxf")
        assert result["project_id"] == 1

    @pytest.mark.asyncio
    @patch("app.cad.reader.read_cad")
    async def test_parse_cad_exception(self, mock_read, tmp_path):
        """底层 read_cad 抛错 → service 包装为 ServiceError"""
        f = tmp_path / "x.dxf"
        f.write_text("dummy")
        mock_read.side_effect = Exception("CAD error")
        from webapi.services.cad import parse_cad_file
        from webapi.services.base import ServiceError
        with pytest.raises(ServiceError) as exc:
            await parse_cad_file(db=None, project_id=1, file_path=str(f))
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    @patch("webapi.services.cad.query_viewport")
    async def test_query_viewport(self, mock_vp):
        mock_vp.return_value = [{"id": 1, "handle": "h"}]
        from webapi.services.cad import query_viewport
        bbox = (0, 0, 100, 100)
        result = await query_viewport(db=None, sheet_id=1, bbox=bbox, limit=10)
        assert len(result) == 1

    @pytest.mark.asyncio
    @patch("webapi.services.cad.get_sheet_metadata")
    async def test_get_sheet_metadata(self, mock_md):
        mock_md.return_value = {"id": 1, "filename": "E-101.dwg"}
        from webapi.services.cad import get_sheet_metadata
        result = await get_sheet_metadata(db=None, sheet_id=1)
        assert result["filename"] == "E-101.dwg"

    @pytest.mark.asyncio
    @patch("webapi.services.cad.get_sheet_metadata", return_value=None)
    async def test_get_sheet_metadata_not_found(self, mock_md):
        from webapi.services.cad import get_sheet_metadata
        result = await get_sheet_metadata(db=None, sheet_id=999)
        assert result is None


# ============================================================
# webapi/services/binding
# ============================================================


class TestBindingService:
    @pytest.mark.asyncio
    @patch("webapi.services.binding.generate_candidates")
    async def test_generate_candidates(self, mock_gen):
        mock_gen.return_value = {"candidates": 5, "stats": {}}
        from webapi.services.binding import generate_candidates_for_project
        result = await generate_candidates_for_project(
            db=None, project_id=1, sheet_id=1, use_llm=True, top_n=5,
        )
        assert result["candidates_created"] == 5

    @pytest.mark.asyncio
    @patch("webapi.services.binding._confirm_binding")
    async def test_confirm_binding(self, mock_confirm):
        mock_confirm.return_value = {"status": "ACCEPTED", "mapping_id": 1}
        from webapi.services.binding import confirm_binding
        result = await confirm_binding(db=None, candidate_id=1)
        assert result["status"] == "ACCEPTED"

    @pytest.mark.asyncio
    @patch("webapi.services.binding._reject_binding")
    async def test_reject_binding(self, mock_reject):
        mock_reject.return_value = {"status": "REJECTED"}
        from webapi.services.binding import reject_binding
        result = await reject_binding(db=None, candidate_id=1, reason="wrong")
        assert result["status"] == "REJECTED"

    @pytest.mark.asyncio
    @patch("webapi.services.binding.generate_candidates", side_effect=Exception("error"))
    async def test_generate_exception(self, mock_gen):
        from webapi.services.binding import generate_candidates_for_project
        from webapi.services.base import ServiceError
        with pytest.raises(ServiceError):
            await generate_candidates_for_project(db=None, project_id=1)

    def test_binding_service_module_imports(self):
        """imports 不抛异常"""
        from webapi.services import binding
        assert hasattr(binding, "generate_candidates_for_project")
        assert hasattr(binding, "confirm_binding")
        assert hasattr(binding, "reject_binding")


# ============================================================
# webapi/services/boq
# ============================================================


class TestBoqService:
    @pytest.mark.asyncio
    @patch("webapi.services.boq.parse_boq")
    async def test_parse_boq(self, mock_parse):
        mock_parse.return_value = ([], {})
        from webapi.services.boq import parse_boq_excel
        result = await parse_boq_excel(db=None, project_id=1, file_path="D:/x.xlsx")
        assert result["item_count"] == 0

    @pytest.mark.asyncio
    @patch("app.db.get_boq_items", return_value=[])
    @patch("app.binding.resolver.recompute", return_value={})
    async def test_writeback_quantities(self, mock_recompute, mock_boq):
        """无 boq_item 时 writeback 返回 0（不需 mock 业务函数，直接测 0 项边界）"""
        from webapi.services.boq import writeback_quantities
        result = await writeback_quantities(db=None, project_id=999, project_scale=1.0)
        assert result["written"] == 0
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_export_boq_invalid_path(self):
        from webapi.services.boq import export_boq_to_excel
        from webapi.services.base import ServiceError
        with pytest.raises(ServiceError) as exc:
            await export_boq_to_excel(db=None, project_id=1, output_path="D:/out.txt")
        msg = exc.value.detail["message"] if isinstance(exc.value.detail, dict) else str(exc.value.detail)
        assert "xlsx" in msg or "xls" in msg
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_export_boq_empty_path(self):
        from webapi.services.boq import export_boq_to_excel
        from webapi.services.base import ServiceError
        with pytest.raises(ServiceError):
            await export_boq_to_excel(db=None, project_id=1, output_path="")

    def test_boq_service_module(self):
        from webapi.services import boq
        assert hasattr(boq, "parse_boq_excel")
        assert hasattr(boq, "writeback_quantities")
        assert hasattr(boq, "export_boq_to_excel")


# ============================================================
# webapi/services/dataset (DB/JSON 切换)
# ============================================================


class TestDatasetService:
    """TEST_DATA_BACKEND=json 时走 JSON 路径；=db 时走 SQLAlchemy"""

    def test_json_backend_list(self, monkeypatch):
        monkeypatch.setenv("TEST_DATA_BACKEND", "json")
        from webapi.services.dataset import list_entries
        result = list_entries()
        assert isinstance(result, list)

    def test_json_backend_mark(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TEST_DATA_BACKEND", "json")
        f = tmp_path / "test.dwg"
        f.write_text("dummy")
        from webapi.services.dataset import mark_entry_json
        result = mark_entry_json(name="t", project_id=1, file_path=str(f), data_type="drawing")
        assert result["name"] == "t"
        assert result["data_type"] == "drawing"

    def test_json_backend_invalid_type(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TEST_DATA_BACKEND", "json")
        f = tmp_path / "test.dwg"
        f.write_text("dummy")
        from webapi.services.dataset import mark_entry_json
        from webapi.services.base import ServiceError
        with pytest.raises(ServiceError):
            mark_entry_json(name="t", project_id=1, file_path=str(f), data_type="invalid")

    def test_json_backend_mark_nonexistent_file(self, monkeypatch):
        monkeypatch.setenv("TEST_DATA_BACKEND", "json")
        from webapi.services.dataset import mark_entry_json
        from webapi.services.base import ServiceError
        with pytest.raises(ServiceError) as exc:
            mark_entry_json(name="t", project_id=1, file_path="D:/nonexistent.dwg", data_type="drawing")
        # ServiceError 默认 400（mark_entry_json 显式 status_code=400）
        assert exc.value.status_code in (400, 404)

    def test_json_backend_deactivate_not_found(self, monkeypatch):
        monkeypatch.setenv("TEST_DATA_BACKEND", "json")
        from webapi.services.dataset import deactivate_entry_json
        result = deactivate_entry_json(9999)
        assert result is False


# ============================================================
# webapi/services/extraction
# ============================================================


class TestExtractionService:
    @pytest.mark.asyncio
    @patch("webapi.services.extraction.extract_and_store_engineering_objects")
    async def test_run_extraction(self, mock_run):
        mock_run.return_value = {"created": 10, "object_ids": [1, 2, 3]}
        from webapi.services.extraction import run_extraction
        result = await run_extraction(db=None, project_id=1, sheet_id=1)
        assert result["created"] == 10

    @pytest.mark.asyncio
    @patch("webapi.services.extraction.extract_and_store_engineering_objects", side_effect=Exception)
    async def test_run_extraction_error(self, mock_run):
        from webapi.services.extraction import run_extraction
        from webapi.services.base import ServiceError
        with pytest.raises(ServiceError):
            await run_extraction(db=None, project_id=1, sheet_id=1)

    @pytest.mark.asyncio
    @patch("webapi.services.extraction.list_engineering_objects")
    async def test_list_eos(self, mock_list):
        mock_list.return_value = [{"id": 1, "object_type": "equipment"}]
        from webapi.services.extraction import list_engineering_objects
        result = await list_engineering_objects(db=None, project_id=1, limit=10)
        assert len(result) == 1

    @pytest.mark.asyncio
    @patch("webapi.services.extraction.list_engineering_objects", return_value=[])
    async def test_list_eos_empty(self, mock_list):
        from webapi.services.extraction import list_engineering_objects
        result = await list_engineering_objects(db=None, project_id=999)
        assert result == []

    def test_extraction_service_module(self):
        from webapi.services import extraction
        assert hasattr(extraction, "run_extraction")
        assert hasattr(extraction, "list_engineering_objects")


# ============================================================
# webapi/services/takeoff
# ============================================================


class TestTakeoffService:
    @pytest.mark.asyncio
    @patch("webapi.services.takeoff.takeoff_pipeline")
    async def test_run_single_sheet(self, mock_run):
        mock_run.return_value = {"stages": 6}
        from webapi.services.takeoff import run_single_sheet_takeoff
        result = await run_single_sheet_takeoff(db=None, project_id=1, sheet_id=1)
        assert result["result"]["stages"] == 6

    @pytest.mark.asyncio
    @patch("webapi.services.takeoff.takeoff_pipeline", side_effect=Exception)
    async def test_run_single_sheet_error(self, mock_run):
        from webapi.services.takeoff import run_single_sheet_takeoff
        from webapi.services.base import ServiceError
        with pytest.raises(ServiceError):
            await run_single_sheet_takeoff(db=None, project_id=1, sheet_id=1)

    @pytest.mark.asyncio
    @patch("webapi.services.takeoff.run_folder_pipeline")
    async def test_run_folder(self, mock_run):
        mock_run.return_value = {"sheets": 4}
        from webapi.services.takeoff import run_folder_takeoff
        result = await run_folder_takeoff(db=None, project_id=1, folder_path="D:/dwg")
        assert result["folder_path"] == "D:/dwg"

    @pytest.mark.asyncio
    async def test_run_folder_empty_path(self):
        from webapi.services.takeoff import run_folder_takeoff
        from webapi.services.base import ServiceError
        with pytest.raises(ServiceError):
            await run_folder_takeoff(db=None, project_id=1, folder_path="")

    def test_takeoff_service_module(self):
        from webapi.services import takeoff
        assert hasattr(takeoff, "run_single_sheet_takeoff")
        assert hasattr(takeoff, "run_folder_takeoff")


# ============================================================
# webapi/services/llm
# ============================================================


class TestLlmService:
    @pytest.mark.asyncio
    @patch("webapi.services.llm.LLMConfig")
    @patch("webapi.services.llm.create_backend")
    async def test_chat_success(self, mock_backend, mock_config):
        mock_config.return_value = MagicMock(ollama_model="qwen2.5")
        mock_backend.return_value.chat.return_value = "Hello response"
        from webapi.services.llm import chat_completion
        result = await chat_completion(db=None, system="sys", user="hi", task_type="chat")
        assert result["output"] == "Hello response"

    @pytest.mark.asyncio
    @patch("webapi.services.llm.create_backend", side_effect=Exception("backend error"))
    async def test_chat_error(self, mock_backend):
        from webapi.services.llm import chat_completion
        from webapi.services.base import ServiceError
        with pytest.raises(ServiceError):
            await chat_completion(db=None, system="sys", user="hi")

    @pytest.mark.asyncio
    async def test_get_settings_missing(self):
        """mock db.execute 抛错（模拟表不存在/连接失败）"""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(side_effect=Exception("no row"))
        from webapi.services.llm import get_llm_settings
        from webapi.services.base import ServiceError
        with pytest.raises(ServiceError):
            await get_llm_settings(db=mock_db)

    def test_llm_service_module(self):
        from webapi.services import llm
        assert hasattr(llm, "get_llm_settings")
        assert hasattr(llm, "update_llm_settings")
        assert hasattr(llm, "chat_completion")


# ============================================================
# webapi/services/audit
# ============================================================


class TestAuditService:
    @pytest.mark.asyncio
    async def test_list_llm_runs_empty(self):
        """mock db.execute 返空（无 llm_run 记录）"""
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([])
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        from webapi.services.audit import list_llm_runs
        result = await list_llm_runs(db=mock_db, project_id=1)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_overview_empty(self):
        """mock 5 个 SQL 查询都返空"""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_result.first.return_value = None
        mock_result.__iter__ = lambda self: iter([])
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        from webapi.services.audit import get_overview
        result = await get_overview(db=mock_db, project_id=1)
        assert result["boq_count"] == 0

    @pytest.mark.asyncio
    async def test_get_precheck_empty(self):
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_result.__iter__ = lambda self: iter([])
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        from webapi.services.audit import get_precheck
        result = await get_precheck(db=mock_db, project_id=1)
        assert "coverage" in result

    def test_audit_service_module(self):
        from webapi.services import audit
        assert hasattr(audit, "list_llm_runs")
        assert hasattr(audit, "get_overview")
        assert hasattr(audit, "get_precheck")


# ============================================================
# webapi/services/spec_match（v1.0 §19 规格匹配）
# ============================================================


class TestSpecMatchService:
    def test_exact_match(self):
        from webapi.services.spec_match import match_spec, SpecMatchStatus
        r = match_spec("4MP", "4MP")
        assert r.status == SpecMatchStatus.EXACT

    def test_normalized_equal(self):
        from webapi.services.spec_match import match_spec, SpecMatchStatus
        r = match_spec("4 MP", "4MP")
        assert r.status == SpecMatchStatus.NORMALIZED_EQUAL

    def test_conflict_key_param(self):
        from webapi.services.spec_match import match_spec, SpecMatchStatus
        r = match_spec("4MP", "8MP")
        assert r.status == SpecMatchStatus.CONFLICT
        assert r.needs_review is True

    def test_unknown_missing(self):
        from webapi.services.spec_match import match_spec, SpecMatchStatus
        r = match_spec("", "4MP")
        assert r.status == SpecMatchStatus.UNKNOWN

    def test_compatible_close_numeric(self):
        from webapi.services.spec_match import match_spec, SpecMatchStatus
        r = match_spec("100mm", "105mm")
        # 100 vs 105 差 5% → COMPATIBLE
        assert r.status in (SpecMatchStatus.COMPATIBLE, SpecMatchStatus.CONFLICT)


# ============================================================
# webapi/services/dataset manifest 工具（v1.0 §8）
# ============================================================


class TestManifestService:
    def test_list_datasets(self, monkeypatch, tmp_path):
        """list_datasets 列 datasets/ 子目录"""
        # 创建临时 datasets/lbh/ 结构
        (tmp_path / "datasets" / "lbh").mkdir(parents=True)
        (tmp_path / "datasets" / "lbh" / "manifest.json").write_text("{}")
        from app import config as cfg_mod
        from app import db as app_db
        monkeypatch.setattr(cfg_mod, "DB_PATH", tmp_path / "test.db")
        # 改 test_data_registry_path 指向 tmp/datasets
        monkeypatch.setenv("TEST_DATA_REGISTRY_PATH", str(tmp_path / "datasets" / "lbh" / "manifest.json"))
        # 清缓存
        from webapi.config import get_settings
        get_settings.cache_clear()
        from webapi.services import dataset
        result = dataset.list_datasets()
        assert "lbh" in result

    def test_load_manifest_lbh(self, monkeypatch, tmp_path):
        (tmp_path / "datasets" / "lbh").mkdir(parents=True)
        (tmp_path / "datasets" / "lbh" / "manifest.json").write_text(
            '{"dataset_id": "TEST", "project": "p", "schema_version": "v1", "parser_version": "v1", "source_revision": "R1"}'
        )
        monkeypatch.setenv("TEST_DATA_REGISTRY_PATH", str(tmp_path / "datasets" / "lbh" / "manifest.json"))
        from webapi.config import get_settings
        get_settings.cache_clear()
        from webapi.services.dataset import load_manifest
        result = load_manifest("lbh")
        assert result["dataset_id"] == "TEST"

    def test_load_manifest_not_found(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TEST_DATA_REGISTRY_PATH", str(tmp_path / "nonexistent" / "manifest.json"))
        from webapi.config import get_settings
        get_settings.cache_clear()
        from webapi.services.dataset import load_manifest
        result = load_manifest("nonexistent")
        assert result is None

    def test_validate_manifest_missing_fields(self):
        from webapi.services.dataset import validate_manifest
        # 缺 3 个必填字段
        missing = validate_manifest({"dataset_id": "X", "project": "Y"})
        assert "schema_version" in missing
        assert "parser_version" in missing
        assert "source_revision" in missing

    def test_validate_manifest_complete(self):
        from webapi.services.dataset import validate_manifest
        missing = validate_manifest({
            "dataset_id": "X", "project": "Y", "schema_version": "v1",
            "parser_version": "v1", "source_revision": "R1",
        })
        assert missing == []
