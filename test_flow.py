import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from schemas.intake_packet import IntakePacket
from services.design_service import run_design
from core.observability import RequestContext
from routers.design import get_ui_cards, produce_files, ProduceRequest
import services.design_store as store

async def main():
    # 1) Create an intake packet representing a car audio run
    intake = IntakePacket(
        subwoofer_model="Test Sub 12",
        diameter_inch=12,
        vehicle="Sedan",
        purpose="SQL",
        rms_power=1000,
        enclosure_type="ported",
        usage_domain="car_audio"
    )
    
    ctx = RequestContext(session_id="test_session", request_id="TEST_RUN_001")
    
    print("--- 1. RUN DESIGN ---")
    result = run_design(intake, ctx)
    acoustic = result.get("acoustic_packet")
    
    if not acoustic:
        print("Design failed.")
        return
        
    print(f"Design ID: {acoustic.design_id}")
    conflict_report = acoustic.conflict_report_dict
    
    with open("conflict_report_dump.json", "w", encoding="utf-8") as f:
        json.dump(conflict_report or {}, f, indent=2, ensure_ascii=False)
    
    print(f"Conflict Report saved to conflict_report_dump.json")

    print("--- 2. GET UI CARDS ---")
    ui_cards_resp = await get_ui_cards(design_id=acoustic.design_id, selected_option="A", use_ai_summary=False)
    
    ui_cards_json = json.loads(ui_cards_resp.body.decode('utf-8'))
    with open("ui_cards_dump.json", "w", encoding="utf-8") as f:
        json.dump(ui_cards_json, f, indent=2, ensure_ascii=False)
        
    print(f"UI Cards JSON saved to ui_cards_dump.json")

    print("--- 3. PRODUCE FILES ---")
    try:
        produce_req = ProduceRequest(
            design_id=acoustic.design_id,
            joint_profile="standard_6mm",
            export_format="DXF",
            material="MDF",
            thickness_mm=18.0
        )
        produce_resp = produce_files(produce_req, x_api_key="internal")
        with open("produce_resp_dump.json", "w", encoding="utf-8") as f:
            json.dump(produce_resp, f, indent=2, ensure_ascii=False)
        print("Produce Response saved to produce_resp_dump.json")
    except Exception as e:
        print(f"Produce failed with exception: {e}")
        try:
            # If it's an HTTPException, we can get detail
            print(f"HTTPException detail: {e.detail}")
        except:
            pass

if __name__ == "__main__":
    asyncio.run(main())
