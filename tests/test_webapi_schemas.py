"""webapi/schemas/ 完整单元测试（9 schema 文件）"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


# ---------- common.py ----------
class TestCommon:
    def test_pagination_valid(self):
        from webapi.schemas.common import Pagination
        p = Pagination(page=1, page_size=20)
        assert p.page == 1
        assert p.page_size == 20

    def test_pagination_page_must_be_positive(self):
        from webapi.schemas.common import Pagination
        with pytest.raises(ValidationError):
            Pagination(page=0, page_size=20)

    def test_pagination_page_size_max(self):
        from webapi.schemas.common import Pagination
        with pytest.raises(ValidationError):
            Pagination(page=1, page_size=500)  # > 200 max

    def test_api_response_default(self):
        from webapi.schemas.common import ApiResponse
        r = ApiResponse()
        assert r.code == 0
        assert r.message == "ok"
        assert r.data is None

    def test_error_response(self):
        from webapi.schemas.common import ErrorDetail, ErrorResponse
        e = ErrorResponse(detail=ErrorDetail(code="test", message="msg"))
        assert e.detail.code == "test"


# ---------- cad.py ----------
class TestCad:
    def test_parse_request(self):
        from webapi.schemas.cad import ParseRequest
        r = ParseRequest(project_id=1, file_path="D:/x.dxf")
        assert r.project_id == 1

    def test_parse_response(self):
        from webapi.schemas.cad import ParseResponse
        r = ParseResponse(project_id=1, file_path="D:/x.dxf", entity_count=100, layer_count=5)
        assert r.entity_count == 100

    def test_viewport_query_required(self):
        from webapi.schemas.cad import ViewportQuery
        with pytest.raises(ValidationError):
            ViewportQuery()  # 缺字段

    def test_viewport_query_defaults(self):
        from webapi.schemas.cad import ViewportQuery
        v = ViewportQuery(sheet_id=1, min_x=0, min_y=0, max_x=100, max_y=100)
        assert v.limit == 10000

    def test_viewport_query_limit_max(self):
        from webapi.schemas.cad import ViewportQuery
        with pytest.raises(ValidationError):
            ViewportQuery(sheet_id=1, min_x=0, min_y=0, max_x=100, max_y=100, limit=100000)

    def test_viewport_entity(self):
        from webapi.schemas.cad import ViewportEntity
        e = ViewportEntity(id=1, handle="h1", dxf_type="LINE", layer="ELV-CCTV")
        assert e.id == 1
        assert e.length == 0.0  # default
        assert e.layer == "ELV-CCTV"


# ---------- binding.py ----------
class TestBinding:
    def test_generate_request_defaults(self):
        from webapi.schemas.binding import GenerateCandidatesRequest
        r = GenerateCandidatesRequest(project_id=1)
        assert r.use_llm is True
        assert r.top_n == 5

    def test_generate_request_top_n_max(self):
        from webapi.schemas.binding import GenerateCandidatesRequest
        with pytest.raises(ValidationError):
            GenerateCandidatesRequest(project_id=1, top_n=100)

    def test_generate_response(self):
        from webapi.schemas.binding import GenerateCandidatesResponse
        r = GenerateCandidatesResponse(
            project_id=1, sheet_id=1, use_llm=True,
            candidates_created=5, stats={},
        )
        assert r.candidates_created == 5

    def test_confirm_request(self):
        from webapi.schemas.binding import ConfirmBindingRequest
        r = ConfirmBindingRequest(candidate_id=1)
        assert r.by_user == "sysadmin"  # default

    def test_binding_candidate_read(self):
        from webapi.schemas.binding import BindingCandidateRead
        r = BindingCandidateRead(
            id=1, project_id=1, engineering_object_id=1, boq_item_id=1,
            method="LLM", score=0.9, confidence=0.8, reason="match", status="PENDING",
        )
        assert r.method == "LLM"


# ---------- boq.py ----------
class TestBoq:
    def test_parse_boq_request(self):
        from webapi.schemas.boq import ParseBoqRequest
        r = ParseBoqRequest(project_id=1, file_path="D:/LBH-001.xlsx")
        assert r.file_path.endswith(".xlsx")

    def test_parse_boq_response(self):
        from webapi.schemas.boq import ParseBoqResponse
        r = ParseBoqResponse(project_id=1, file_path="D:/LBH-001.xlsx", item_count=480, meta={})
        assert r.item_count == 480

    def test_writeback_request_default_scale(self):
        from webapi.schemas.boq import WritebackRequest
        r = WritebackRequest(project_id=1)
        assert r.project_scale == 1.0

    def test_writeback_response(self):
        from webapi.schemas.boq import WritebackResponse
        r = WritebackResponse(project_id=1, written=100, failed=5)
        assert r.written == 100

    def test_boq_item_read_b2_6_fields(self):
        """B2 6 字段模型"""
        from webapi.schemas.boq import BoqItemRead
        r = BoqItemRead(
            id=1, project_id=1, row_index=1,
            section="CABLE", item_key="r1", code="r1", description="Cable",
            brand="BrandX", unit="m",
            bill_qty=100.0, installed_qty=50.0, qty_remaining=50.0,
            original_qty=100.0, rule_type="length", scale_factor=1.0, measured_qty=0.0,
        )
        assert r.section == "CABLE"
        assert r.item_key == "r1"
        assert r.bill_qty == 100.0
        assert r.qty_remaining == 50.0


# ---------- dataset.py ----------
class TestDataset:
    def test_test_data_entry_defaults(self):
        from webapi.schemas.dataset import TestDataEntry
        e = TestDataEntry(
            name="t", project_id=1, file_path="D:/x.dwg", data_type="drawing",
        )
        assert e.is_active is True
        assert e.note == ""

    def test_test_data_entry_invalid_data_type(self):
        # data_type 没枚举限制（自由字段）
        from webapi.schemas.dataset import TestDataEntry
        e = TestDataEntry(name="t", project_id=1, file_path="D:/x.dwg", data_type="any")
        assert e.data_type == "any"


# ---------- extraction.py ----------
class TestExtraction:
    def test_extraction_request(self):
        from webapi.schemas.extraction import ExtractionRequest
        r = ExtractionRequest(project_id=1, sheet_id=1)
        assert r.layer_rules == {}  # default

    def test_extraction_response(self):
        from webapi.schemas.extraction import ExtractionResponse
        r = ExtractionResponse(project_id=1, sheet_id=1, created=10, stats={}, object_ids=[1, 2])
        assert r.created == 10

    def test_engineering_object_read(self):
        from webapi.schemas.extraction import EngineeringObjectRead
        r = EngineeringObjectRead(
            id=1, project_id=1, sheet_id=1, object_type="equipment",
            discipline="ELV", system="CCTV", block_name="CAM_DOME",
            layer_name="ELV-CCTV", specification="4MP", unit="No.",
            quantity_rule="count", confidence=0.9, source="rule",
        )
        assert r.object_type == "equipment"
        assert r.confidence == 0.9


# ---------- takeoff.py ----------
class TestTakeoff:
    def test_takeoff_request_minimal(self):
        from webapi.schemas.takeoff import TakeoffRequest
        r = TakeoffRequest(project_id=1)
        assert r.sheet_id is None
        assert r.folder_path == ""

    def test_takeoff_request_with_sheet(self):
        from webapi.schemas.takeoff import TakeoffRequest
        r = TakeoffRequest(project_id=1, sheet_id=5)
        assert r.sheet_id == 5

    def test_takeoff_response(self):
        from webapi.schemas.takeoff import TakeoffResponse
        r = TakeoffResponse(project_id=1, result={"stages": 6})
        assert r.result["stages"] == 6


# ---------- llm.py ----------
class TestLlm:
    def test_llm_settings_read_defaults(self):
        from webapi.schemas.llm import LlmSettingsRead
        r = LlmSettingsRead()
        assert r.id == 1
        assert r.active_backend == "ollama"
        assert r.temperature == 0.1
        assert r.timeout == 120
        assert r.max_tokens == 4000

    def test_llm_settings_update_partial(self):
        from webapi.schemas.llm import LlmSettingsUpdate
        r = LlmSettingsUpdate(active_backend="openai", temperature=0.5)
        assert r.active_backend == "openai"
        assert r.temperature == 0.5
        # 其他字段 None（partial update）
        assert r.timeout is None

    def test_chat_request_minimal(self):
        from webapi.schemas.llm import ChatRequest
        r = ChatRequest(user="hello")
        assert r.system == ""
        assert r.task_type == "chat"
        assert r.images == []

    def test_chat_response(self):
        from webapi.schemas.llm import ChatResponse
        r = ChatResponse(task_type="chat", model="qwen2.5", output="hi")
        assert r.model == "qwen2.5"


# ---------- audit.py ----------
class TestAudit:
    def test_llm_run_read_minimal(self):
        from webapi.schemas.audit import LlmRunRead
        r = LlmRunRead(
            id=1, project_id=1, task_type="binding", model="qwen",
            created_at="2026-09-06T10:00:00",
        )
        assert r.status == "ok"
        assert r.duration_ms == 0

    def test_overview_response(self):
        from webapi.schemas.audit import OverviewResponse
        r = OverviewResponse(
            project_id=1, boq_count=100, mapping_count=80,
            eo_breakdown=[], writeback_by_takability=[], llm_runs_by_task=[],
        )
        assert r.boq_count == 100
