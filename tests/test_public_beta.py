"""Halka acik beta arayuzu ile DD1 API arasindaki sozlesme testleri."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_public_beta_end_to_end(monkeypatch, tmp_path: Path):
    woofer_db = tmp_path / "woofers.json"
    woofer_db.write_text(json.dumps([{
        "model": "Beta Test 12D2",
        "brand": "Test Marka",
        "dia_mm": 300,
        "fs": 31.0,
        "qts": 0.28,
        "vas": 74.0,
        "xmax_mm": 12.5,
        "power_w": 800,
    }]), encoding="utf-8")

    monkeypatch.setenv("DD1_ENV", "test")
    monkeypatch.setenv("DD1_PUBLIC_BETA_MODE", "true")
    monkeypatch.setenv("DD1_WOOFER_DB", str(woofer_db))
    monkeypatch.setenv("DD1_APPROVED_MODELS", "Beta Test 12D2")
    monkeypatch.delenv("DD1_ADMIN_KEY", raising=False)

    from main import app
    import core.learning_engine as learning_engine
    import services.design_store as design_store

    archive = tmp_path / "design_archive.json"
    feedback = tmp_path / "feedback_log.json"
    exports = tmp_path / "exports"

    monkeypatch.setattr(design_store, "_BASE", tmp_path)
    monkeypatch.setattr(design_store, "_ARCHIVE", archive)
    monkeypatch.setattr(design_store, "_EXPORTS_DIR", exports)
    monkeypatch.setattr(design_store, "_CACHE", {})
    monkeypatch.setattr(design_store, "_LOADED", False)
    monkeypatch.setattr(learning_engine, "FEEDBACK", feedback)

    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            home = await client.get("/")
            assert home.status_code == 200
            assert "Aracına uygun subwoofer kabinini hesapla" in home.text
            assert "POST /design" not in home.text
            assert "frame-ancestors 'none'" in home.headers["content-security-policy"]
            assert (await client.get("/styles.css")).status_code == 200
            assert (await client.get("/app.js")).status_code == 200

            catalog = await client.get("/api/public/products")
            assert catalog.status_code == 200
            catalog_body = catalog.json()
            assert catalog_body["count"] == 1
            assert catalog_body["results"][0]["model"] == "Beta Test 12D2"
            assert "fs" not in catalog_body["results"][0]
            assert "qts" not in catalog_body["results"][0]

            rejected = await client.post("/api/public/design", json={
                "woofer_model": "Onaysiz Model",
            })
            assert rejected.status_code == 400

            tampered = await client.post("/api/public/design", json={
                "woofer_model": "Beta Test 12D2",
                "vehicle": "Sedan",
                "purpose": "SQL",
                "max_width_mm": 900,
                "max_height_mm": 450,
                "max_depth_mm": 550,
                "fs": 199,
            })
            assert tampered.status_code == 422

            design = await client.post("/api/public/design", json={
                "woofer_model": "Beta Test 12D2",
                "vehicle": "Sedan",
                "purpose": "SQL",
                "max_width_mm": 900,
                "max_height_mm": 450,
                "max_depth_mm": 550,
            })
            assert design.status_code == 200, design.text
            result = design.json()
            assert result["material_thickness_mm"] == 10
            assert result["kerf_mm"] == 0.15
            assert result["port"]["area_cm2"] > 10
            assert result["port"]["length_cm"] > 1
            assert result["panel_list"]
            assert result["fit_check"]["status"] == "fits"
            assert "peak_spl_db" not in result
            assert isinstance(result["geometry_review_required"], bool)

            feedback_response = await client.post("/api/public/feedback", json={
                "design_id": result["design_id"],
                "rating": 5,
                "comment": "Sonuc uygun",
                "woofer_model": "Beta Test 12D2",
                "vehicle": "Sedan",
                "purpose": "SQL",
            })
            assert feedback_response.status_code == 200
            assert feedback.exists()

            product_request = await client.post("/api/public/feedback", json={
                "design_id": "catalog_request",
                "rating": 3,
                "comment": "Urun talebi: Yeni Test Modeli",
                "woofer_model": "Yeni Test Modeli",
            })
            assert product_request.status_code == 200
            feedback_rows = json.loads(feedback.read_text(encoding="utf-8"))
            assert [row["kind"] for row in feedback_rows] == [
                "design_feedback",
                "product_request",
            ]

            assert (await client.get("/woofers/search", params={"q": "Test"})).status_code == 404
            assert (await client.get("/feedback/report")).status_code == 404
            assert (await client.get("/docs")).status_code == 404

        assert archive.exists()

    asyncio.run(scenario())
