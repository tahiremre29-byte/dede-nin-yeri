import os
from pathlib import Path
from typing import Dict
# We import run_design and get_acoustic from the core service
from services.design_service import run_design, get_acoustic
from schemas.intake_packet import build_intake

def calculate_acoustic_bridge(payload: Dict) -> Dict:
    """Thin adapter for acoustic calculation ONLY.
    * Takes user parameters.
    * Runs the acoustic design engine.
    * The engine handles saving the AcousticPacket internally.
    * Returns the generated design_id.
    """
    intake = build_intake(
        raw_message="",
        intent="kabin_tasarim",
        vehicle=payload.get("vehicle", "Sedan"),
        purpose=payload.get("purpose", "home"),
        diameter_inch=payload.get("diameter_inch", 8),
        rms_power=payload.get("rms_power", 100),
        woofer_model=payload.get("woofer_model"),
        ts=None,
        enclosure_type=payload.get("port_type", "ported"),
        usage_domain=payload.get("usage_domain", "home_audio"),
        bass_char=payload.get("bass_char", "SQL"),
    )
    # This automatically calls store_acoustic and returns a dictionary with the acoustic_packet
    result = run_design(intake)
    
    if not result.get("success"):
        raise ValueError(f"Acoustic calculation failed: {result.get('errors')}")
        
    packet = result.get("acoustic_packet")
    if not packet:
        raise ValueError("Acoustic packet was not generated.")

    # Log to audit history
    from services.history_service import history_db
    session_id = payload.get("session_id", "unknown_session")
    history_db.log_calculation(
        session_id=session_id,
        design_id=packet.design_id, 
        input_payload=payload, 
        acoustic_packet=packet.dict() if hasattr(packet, 'dict') else vars(packet)
    )

    return {
        "design_id": packet.design_id,
        "message": "Acoustic calculation successful and locked.",
        "summary": result.get("summary"),
        "net_volume_l": packet.net_volume_l,
        "tuning_hz": packet.tuning_hz
    }

def produce_dxf_bridge(design_id: str, output_dir: Path, session_id: str = None) -> Dict:
    """Thin adapter for Production ONLY.
    * Receives a specific design_id.
    * Retrieves the locked acoustic packet.
    * Directly applies it to create a DXF. NO acoustical modifications allowed!
    """
    packet = get_acoustic(design_id)
    if not packet:
        raise ValueError(f"No acoustic design found for ID {design_id}. Calculation must complete first.")
        
    # Temporary dump implementation for the spike, honoring the calculated values
    dxf_path = output_dir / f"{design_id}.dxf"
    
    # In a real implementation, this would call core.handoff_to_production
    content = f"DXF Design: {design_id}\n"
    content += f"Liters: {packet.net_volume_l}\n"
    content += f"Port: {packet.tuning_hz} Hz\n"
    content += f"STRICTLY FOLLOW ACOUSTIC PARAMETERS\n"
    
    dxf_path.write_text(content, encoding="utf-8")
    
    from services.history_service import history_db
    history_db.log_production(
        session_id=session_id,
        design_id=design_id, 
        status="success", 
        output_file=dxf_path.name
    )
    
    return {
        "design_id": design_id,
        "message": f"DXF generated at {dxf_path.name} strictly following locked acoustic parameters.",
        "download_url": f"/api/design/download/{design_id}",
    }
