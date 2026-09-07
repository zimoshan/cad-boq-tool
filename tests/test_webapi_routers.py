"""webapi 路由集成测试（FastAPI TestClient + mock services）

策略：mock 所有 service 层函数返回值（避免真 DB / 真 LLM / 真 ODA 依赖）
覆盖：35 routes × 1-3 case = ~50 case
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert "cad-boq-tool" in data["name"]


def test_openapi_docs(client):
    r = client.get("/docs")
    assert r.status_code == 200
    r2 = client.get("/openapi.json")
    assert r2.status_code == 200
    spec = r2.json()
    assert "/health" in spec["paths"]


# ---------- /api/cad ----------

@patch("webapi.routers.cad.cad_service.parse_cad_file", new_callable=AsyncMock)
def test_cad_parse_404_file_not_found(mock_parse, client):
    from webapi.services.base import ServiceError
    mock_parse.side_effect = ServiceError("File #D:/x.dxf not found", status_code=404, code="not_found")
    r = client.post("/api/cad/parse", json={"project_id": 1, "file_path": "D:/x.dxf"})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "not_found"


@patch("webapi.routers.cad.cad_service.parse_cad_file", new_callable=AsyncMock)
def test_cad_parse_ok(mock_parse, client):
    mock_parse.return_value = {"project_id": 1, "file_path": "D:/x.dxf", "entity_count": 100, "layer_count": 5}
    r = client.post("/api/cad/parse", json={"project_id": 1, "file_path": "D:/x.dxf"})
    assert r.status_code == 200
    assert r.json()["entity_count"] == 100


@patch("webapi.routers.cad.cad_service.query_viewport", new_callable=AsyncMock)
def test_cad_viewport(mock_vp, client):
    mock_vp.return_value = [{"id": 1, "handle": "h1", "dxf_type": "LINE"}]
    r = client.post("/api/cad/viewport", json={"sheet_id": 1, "min_x": 0, "min_y": 0, "max_x": 100, "max_y": 100})
    assert r.status_code == 200
    assert r.json()["total"] == 1


@patch("webapi.routers.cad.cad_service.get_sheet_metadata", new_callable=AsyncMock)
def test_cad_metadata_ok(mock_md, client):
    mock_md.return_value = {
        "id": 1, "project_id": 1, "filename": "E-101.dwg",
        "drawing_type": "plan", "units": "mm", "level": "L01",
    }
    r = client.get("/api/cad/metadata?sheet_id=1")
    assert r.status_code == 200
    assert r.json()["drawing_type"] == "plan"


@patch("webapi.routers.cad.cad_service.get_sheet_metadata", new_callable=AsyncMock)
def test_cad_metadata_404(mock_md, client):
    mock_md.return_value = None
    r = client.get("/api/cad/metadata?sheet_id=999")
    assert r.status_code == 404


@patch("webapi.routers.cad.cad_service.get_sheet_layers", new_callable=AsyncMock)
def test_cad_layers(mock_layers, client):
    mock_layers.return_value = [{"layer": "ELV-CCTV", "entity_count": 100}]
    r = client.get("/api/cad/layers?sheet_id=1")
    assert r.status_code == 200
    assert r.json()["items"][0]["layer"] == "ELV-CCTV"


@patch("webapi.routers.cad.cad_service.get_sheet_blocks", new_callable=AsyncMock)
def test_cad_blocks(mock_blocks, client):
    mock_blocks.return_value = [{"block_name": "CAM_DOME", "insert_count": 10}]
    r = client.get("/api/cad/blocks?sheet_id=1")
    assert r.status_code == 200
    assert r.json()["items"][0]["insert_count"] == 10


@patch("webapi.routers.cad.cad_service.list_entities", new_callable=AsyncMock)
def test_cad_entities_pagination(mock_ents, client):
    mock_ents.return_value = [{"id": 1, "handle": "h", "dxf_type": "LINE"}]
    r = client.get("/api/cad/entities?sheet_id=1&layer=ELV-CCTV&limit=10&offset=0")
    assert r.status_code == 200
    assert r.json()["limit"] == 10


# ---------- /api/binding ----------

@patch("webapi.routers.binding.binding_service.generate_candidates_for_project", new_callable=AsyncMock)
def test_binding_generate(mock_gen, client):
    mock_gen.return_value = {
        "project_id": 1, "sheet_id": 1, "use_llm": True,
        "candidates_created": 5, "stats": {},
    }
    r = client.post("/api/binding/generate", json={"project_id": 1, "sheet_id": 1, "use_llm": True, "top_n": 5})
    assert r.status_code == 200
    assert r.json()["candidates_created"] == 5
    assert r.json()["use_llm"] is True


@patch("webapi.routers.binding.binding_service.confirm_binding", new_callable=AsyncMock)
def test_binding_confirm(mock_confirm, client):
    mock_confirm.return_value = {"status": "ACCEPTED", "mapping_id": 1}
    r = client.post("/api/binding/confirm", json={"candidate_id": 1})
    assert r.status_code == 200


@patch("webapi.routers.binding.binding_service.reject_binding", new_callable=AsyncMock)
def test_binding_reject(mock_reject, client):
    mock_reject.return_value = {"status": "REJECTED"}
    r = client.post("/api/binding/reject", json={"candidate_id": 1, "reason": "wrong mapping"})
    assert r.status_code == 200


# ---------- /api/boq ----------

@patch("webapi.routers.boq.boq_service.parse_boq_excel", new_callable=AsyncMock)
def test_boq_parse_404(mock_parse, client):
    from webapi.services.base import ServiceError
    mock_parse.side_effect = ServiceError("File not found", status_code=404, code="file_not_found")
    r = client.post("/api/boq/parse", json={"project_id": 1, "file_path": "D:/x.xlsx"})
    assert r.status_code == 404


@patch("webapi.routers.boq.boq_service.parse_boq_excel", new_callable=AsyncMock)
def test_boq_parse_ok(mock_parse, client):
    mock_parse.return_value = {
        "project_id": 1, "file_path": "D:/LBH-001.xlsx",
        "item_count": 480, "meta": {},
    }
    r = client.post("/api/boq/parse", json={"project_id": 1, "file_path": "D:/LBH-001.xlsx"})
    assert r.status_code == 200
    assert r.json()["item_count"] == 480
    assert r.json()["file_path"] == "D:/LBH-001.xlsx"


@patch("webapi.routers.boq.boq_service.writeback_quantities", new_callable=AsyncMock)
def test_boq_writeback(mock_wb, client):
    mock_wb.return_value = {"project_id": 1, "written": 100, "failed": 0}
    r = client.post("/api/boq/writeback", json={"project_id": 1, "project_scale": 1.0})
    assert r.status_code == 200
    assert r.json()["written"] == 100


@patch("webapi.routers.boq.boq_service.export_boq_to_excel", new_callable=AsyncMock)
def test_boq_export(mock_export, client):
    """v1.0 §15 工程量回写：导出实测值到 Excel"""
    mock_export.return_value = {
        "project_id": 1, "output_path": "D:/out.xlsx",
        "written_rows": 100, "skipped_rows": 0,
        "by_takability": {"MEASURABLE": 80, "NO_DRAWING": 20},
    }
    r = client.post("/api/boq/export", json={"project_id": 1, "output_path": "D:/out.xlsx"})
    assert r.status_code == 200
    assert r.json()["written_rows"] == 100
    assert r.json()["by_takability"]["MEASURABLE"] == 80


@patch("webapi.routers.boq.boq_service.export_boq_to_excel", new_callable=AsyncMock)
def test_boq_export_invalid_path(mock_export, client):
    """output_path 必须 .xlsx/.xls"""
    from webapi.services.base import ServiceError
    mock_export.side_effect = ServiceError("must be .xlsx or .xls", code="invalid_input")
    r = client.post("/api/boq/export", json={"project_id": 1, "output_path": "D:/out.txt"})
    assert r.status_code == 400


# ---------- /api/dataset ----------

def test_dataset_list_empty(client):
    r = client.get("/api/dataset")
    assert r.status_code == 200
    data = r.json()
    assert "entries" in data
    assert "backend" in data


def test_dataset_mark_404(client, tmp_path):
    """mark 不存在文件 → 404"""
    from webapi.services.base import ServiceError
    with patch("webapi.routers.dataset.dataset_service.mark_entry_json", side_effect=ServiceError("File not found", status_code=404, code="file_not_found")):
        r = client.post(
            "/api/dataset/mark",
            json={"name": "test", "project_id": 1, "file_path": str(tmp_path / "nonexistent.dwg"), "data_type": "drawing"},
        )
    assert r.status_code == 404


def test_dataset_mark_invalid_type(client, tmp_path):
    f = tmp_path / "test.dwg"
    f.write_text("dummy")
    from webapi.services.base import ServiceError
    with patch("webapi.routers.dataset.dataset_service.mark_entry_json", side_effect=ServiceError("Invalid data_type", code="invalid_data_type")):
        r = client.post(
            "/api/dataset/mark",
            json={"name": "t", "project_id": 1, "file_path": str(f), "data_type": "invalid"},
        )
    # ServiceError 默认 400
    assert r.status_code == 400


def test_dataset_deactivate(client):
    r = client.post("/api/dataset/deactivate", json={"entry_id": 999})
    assert r.status_code == 200
    assert r.json()["ok"] is False  # 不存在


# ---------- /api/jobs ----------

def test_jobs_list_empty(client):
    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert "jobs" in r.json()


def test_jobs_get_404(client):
    r = client.get("/api/jobs/nonexistent")
    assert r.status_code == 404


@patch("webapi.routers.jobs.job_manager.submit_by_name", new_callable=AsyncMock)
def test_jobs_submit(mock_submit, client):
    from webapi.jobs.models import Job, JobStatus
    job = Job(id="test123", name="test", status=JobStatus.PENDING)
    mock_submit.return_value = job
    r = client.post("/api/jobs/submit", json={"name": "test", "func_name": "boq.parse", "payload": {}})
    assert r.status_code == 200
    assert r.json()["id"] == "test123"

@patch("webapi.routers.jobs.job_manager.submit_by_name", new_callable=AsyncMock)
def test_jobs_submit_missing_func_name_422(mock_submit, client):
    r = client.post("/api/jobs/submit", json={"name": "test", "payload": {}})
    assert r.status_code == 422
    mock_submit.assert_not_called()


# ---------- /api/extraction ----------

@patch("webapi.routers.extraction.extraction_service.run_extraction", new_callable=AsyncMock)
def test_extraction_run(mock_run, client):
    mock_run.return_value = {"project_id": 1, "sheet_id": 1, "created": 10, "stats": {}, "object_ids": [1, 2, 3]}
    r = client.post("/api/extraction/run", json={"project_id": 1, "sheet_id": 1})
    assert r.status_code == 200
    assert r.json()["created"] == 10


@patch("webapi.routers.extraction.extraction_service.list_engineering_objects", new_callable=AsyncMock)
def test_extraction_list_eos(mock_list, client):
    """返回 EngineeringObjectRead schema 必需字段"""
    mock_list.return_value = [{
        "id": 1, "project_id": 1, "sheet_id": 1,
        "object_type": "equipment", "discipline": "ELV", "system": "CCTV",
        "block_name": "CAM_DOME", "layer_name": "ELV-CCTV",
        "specification": "4MP", "unit": "No.",
        "quantity_rule": "count", "confidence": 0.9, "source": "rule",
    }]
    r = client.get("/api/extraction/eos?project_id=1&object_type=equipment")
    assert r.status_code == 200
    assert r.json()[0]["discipline"] == "ELV"


# ---------- /api/takeoff ----------

@patch("webapi.routers.takeoff.takeoff_service.run_single_sheet_takeoff", new_callable=AsyncMock)
def test_takeoff_run_single(mock_run, client):
    mock_run.return_value = {"project_id": 1, "sheet_id": 1, "result": {"stages": 6}}
    r = client.post("/api/takeoff/run", json={"project_id": 1, "sheet_id": 1})
    assert r.status_code == 200


# ---------- /api/audit ----------

@patch("webapi.routers.audit.audit_service.list_llm_runs", new_callable=AsyncMock)
def test_audit_llm_runs(mock_runs, client):
    mock_runs.return_value = [{"id": 1, "task_type": "binding", "model": "qwen"}]
    r = client.get("/api/audit/llm-runs?project_id=1")
    assert r.status_code == 200
    assert r.json()["items"][0]["task_type"] == "binding"


@patch("webapi.routers.audit.audit_service.get_overview", new_callable=AsyncMock)
def test_audit_overview(mock_ov, client):
    mock_ov.return_value = {
        "project_id": 1, "boq_count": 100, "mapping_count": 80,
        "eo_breakdown": [], "writeback_by_takability": [],
        "llm_runs_by_task": [],
    }
    r = client.get("/api/audit/overview?project_id=1")
    assert r.status_code == 200
    assert r.json()["boq_count"] == 100


@patch("webapi.routers.audit.audit_service.get_precheck", new_callable=AsyncMock)
def test_audit_precheck(mock_pc, client):
    mock_pc.return_value = {
        "project_id": 1, "drawing_type": [], "takability": [],
        "coverage": {"total_boq": 100, "boq_coverage_pct": 80.0},
        "granularity": {"n_sheets": 4, "avg_entity_per_sheet": 20000.0},
        "version": [], "provisional_count": 0,
    }
    r = client.get("/api/audit/precheck?project_id=1")
    assert r.status_code == 200
    assert r.json()["coverage"]["boq_coverage_pct"] == 80.0


# ---------- /api/dataset manifest 端点（v1.0 §8） ----------

def test_dataset_manifests_list(client):
    """列出 datasets/ 目录下所有 dataset_id"""
    r = client.get("/api/dataset/manifests")
    assert r.status_code == 200
    data = r.json()
    assert "datasets" in data
    assert isinstance(data["datasets"], list)


def test_dataset_manifest_get_lbh(client, monkeypatch):
    """读 lbh manifest（设 TEST_DATA_REGISTRY_PATH 指向项目根）"""
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    monkeypatch.setenv("TEST_DATA_REGISTRY_PATH", os.path.join(project_root, "datasets", "lbh", "manifest.json"))
    from webapi.config import get_settings
    get_settings.cache_clear()
    r = client.get("/api/dataset/manifest?dataset_id=lbh")
    assert r.status_code == 200
    data = r.json()
    assert "manifest" in data
    assert data["manifest"]["dataset_id"] == "LBH-2026-08"
    assert data["valid"] is True
    assert data["missing_fields"] == []


def test_dataset_manifest_404(client, monkeypatch):
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    monkeypatch.setenv("TEST_DATA_REGISTRY_PATH", os.path.join(project_root, "datasets", "lbh", "manifest.json"))
    from webapi.config import get_settings
    get_settings.cache_clear()
    r = client.get("/api/dataset/manifest?dataset_id=nonexistent")
    assert r.status_code == 404


def test_dataset_manifest_update_field(client, monkeypatch):
    """更新 manifest 单字段（schema_version）"""
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    monkeypatch.setenv("TEST_DATA_REGISTRY_PATH", os.path.join(project_root, "datasets", "lbh", "manifest.json"))
    from webapi.config import get_settings
    get_settings.cache_clear()
    r = client.post(
        "/api/dataset/manifest",
        json={"dataset_id": "lbh", "key": "schema_version", "value": "cad-1.0"},
    )
    assert r.status_code == 200
    assert r.json()["updated"] is True
    assert r.json()["manifest"]["schema_version"] == "cad-1.0"


# ---------- /api/cad-standard 5 规则端点（v1.0 §26） ----------

def test_cad_standard_list_rules(client):
    r = client.get("/api/cad-standard/rules")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 5  # 5 个 JSON 文件
    assert "layer_rules.json" in data["files"]
    assert "specification_rules.json" in data["files"]


def test_cad_standard_get_layer_rules(client):
    r = client.get("/api/cad-standard/rules/layer_rules")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "layer_rules.json"
    assert "rules" in data["content"]
    assert "blacklist_layers" in data["content"]


def test_cad_standard_update_rule(client, tmp_path, monkeypatch):
    """更新规则（写 tmp 目录避免污染真实文件）"""
    import json

    # 准备：复制真实规则到 tmp 目录
    # 直接 patch routers/cad_standard._standard_dir 返回 tmp
    src = Path(__file__).parent.parent / "webapi" / "cad_standard" / "specification_rules.json"
    target = tmp_path / "specification_rules.json"
    target.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    with patch("webapi.routers.cad_standard._standard_dir", return_value=tmp_path):
        r = client.put(
            "/api/cad-standard/rules/specification_rules",
            json={"content": {
                "_doc": "test update",
                "_schema_version": "cad-1.0",
                "states": {"TEST": "test"},
                "rules": [],
            }},
        )
    assert r.status_code == 200
    assert r.json()["updated"] is True
    # 验证 tmp 文件被更新
    new_content = json.loads(target.read_text(encoding="utf-8"))
    assert new_content["_doc"] == "test update"


def test_cad_standard_update_unknown_rule_400(client):
    r = client.put(
        "/api/cad-standard/rules/unknown_file",
        json={"content": {"foo": "bar"}},
    )
    assert r.status_code == 400


def test_cad_standard_404(client):
    r = client.get("/api/cad-standard/rules/nonexistent_file")
    assert r.status_code == 404


# ---------- RBAC 装饰器端到端（简化版：仅校验不抛 403） ----------

def test_no_login_decorator_does_not_403(client, monkeypatch):
    """AUTH_MODE=no_login 默认下，jobs/list 不应 403"""
    r = client.get("/api/jobs")
    # no_login 直接放行；非 403 即通过
    assert r.status_code != 403


# ---------- 错误响应格式 ----------

@patch("webapi.routers.cad.cad_service.parse_cad_file", new_callable=AsyncMock)
def test_service_error_format(mock_parse, client):
    from webapi.services.base import ServiceError
    mock_parse.side_effect = ServiceError("validation failed", status_code=422, code="invalid")
    r = client.post("/api/cad/parse", json={"project_id": 1, "file_path": "D:/x.dxf"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["code"] == "invalid"
    assert "validation failed" in detail["message"]
