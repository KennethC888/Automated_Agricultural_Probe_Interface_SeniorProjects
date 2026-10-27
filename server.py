import asyncio
from datetime import datetime
import random
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Rover Base Station Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Known field map for soil probe stations
FIELD_MAP = {
    1: {"name": "Zone A - Bed 1", "x": 5.0, "y": 0.0},
    2: {"name": "Zone B - Bed 2", "x": 10.0, "y": 2.5},
    3: {"name": "Zone C - Bed 3", "x": 15.0, "y": -1.0},
}

class TelemetryPayload(BaseModel):
    event_type: str
    tag_id: Optional[int] = None
    qr_data: Optional[str] = None
    distance_cm: Optional[float] = None
    heading_deg: Optional[float] = None

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WS] Client connected. Total active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"[WS] Client disconnected. Total active: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# Prevent re-triggering repeatedly while the rover stays in front of the tag
active_probing_lock = False
recently_probed_tags = set()

# ------------------------------------------------------------------
# Soil Probing & LoRa Simulation Routine
# ------------------------------------------------------------------
async def execute_probe_and_lora_transmission(tag_id: int, zone_name: str):
    """
    Simulates:
    1. Lowering the linear actuator probe into the soil.
    2. Taking sensor readings (moisture, soil temp, pH).
    3. Packaging and sending the data over LoRa protocol (915 MHz).
    4. Base station receiving and parsing the RF packet.
    """
    global active_probing_lock
    active_probing_lock = True
    
    print("\n" + "="*60)
    print(f"🚜 [ROVER ACTUATOR] AprilTag {tag_id} Reached ({zone_name})")
    print("🚜 [ROVER ACTUATOR] Lowering probe actuator into soil...")
    await asyncio.sleep(1.2)  # Simulate motor insertion time
    
    print("🔬 [SENSORS] Sampling soil moisture, temperature, and pH...")
    await asyncio.sleep(0.8)  # Sensor stabilization delay
    
    # 1. Generate realistic randomized agricultural readings
    moisture_pct = round(random.uniform(18.5, 34.0), 1)
    temp_c = round(random.uniform(16.0, 24.5), 1)
    temp_f = round((temp_c * 9/5) + 32, 1)
    ph_level = round(random.uniform(6.3, 7.4), 2)
    
    print(f"    ├─ Soil Moisture:    {moisture_pct}%")
    print(f"    ├─ Soil Temperature: {temp_c}°C ({temp_f}°F)")
    print(f"    └─ Soil pH:          {ph_level}")

    print("🚜 [ROVER ACTUATOR] Retracting probe to travel position...")
    await asyncio.sleep(1.0)

    # 2. Package into a simulated LoRa physical-layer transmission packet
    # Typical LoRa parameters: 915 MHz, SF7, BW 125kHz, CR 4/5
    simulated_rssi = random.randint(-98, -62)  # Received Signal Strength Indicator in dBm
    simulated_snr = round(random.uniform(6.5, 11.0), 1)  # Signal-to-Noise Ratio in dB
    
    lora_packet = {
        "network": "LoRa_P2P",
        "frequency_mhz": 915.0,
        "spreading_factor": "SF7",
        "rssi_dbm": simulated_rssi,
        "snr_db": simulated_snr,
        "payload": {
            "node_id": "ROVER_01",
            "station_id": tag_id,
            "zone": zone_name,
            "soil_moisture_pct": moisture_pct,
            "soil_temp_c": temp_c,
            "soil_temp_f": temp_f,
            "ph": ph_level,
            "battery_v": round(random.uniform(11.8, 12.4), 2),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    }
    
    print(f"📡 [LoRa TX] Rover broadcasting RF packet on 915.0 MHz (SF7)...")
    await asyncio.sleep(0.4)  # Over-the-air time-on-air (ToA) delay
    
    print(f"📥 [LoRa RX] BASE STATION RECEIVED PACKET:")
    print(f"    ├─ Signal Quality: RSSI={simulated_rssi} dBm | SNR={simulated_snr} dB")
    print(f"    └─ Payload Data:   {lora_packet['payload']}")
    print("="*60 + "\n")

    # 3. Notify the web dashboard via WebSocket
    await manager.broadcast({
        "event": "probe_complete",
        "tag_id": tag_id,
        "zone": zone_name,
        "lora_meta": {
            "frequency": "915.0 MHz",
            "rssi": f"{simulated_rssi} dBm",
            "snr": f"{simulated_snr} dB"
        },
        "readings": {
            "moisture_pct": moisture_pct,
            "temperature_c": temp_c,
            "temperature_f": temp_f,
            "ph_level": ph_level
        },
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

    # Keep tag in cooldown for 8 seconds so it doesn't trigger 50 times in a row
    await asyncio.sleep(8.0)
    recently_probed_tags.discard(tag_id)
    active_probing_lock = False

# ------------------------------------------------------------------
# Static HTML Route
# ------------------------------------------------------------------
@app.get("/")
async def serve_index():
    return FileResponse("index.html")

@app.get("/api/field-map")
async def get_field_map():
    return {"status": "ok", "map": FIELD_MAP}

# ------------------------------------------------------------------
# WebSocket Endpoint
# ------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            event = data.get("event")

            if event == "apriltag_detected":
                tag_id = data.get("tag_id")
                dist = data.get("distance_cm")
                heading = data.get("heading_deg")

                # If within 50cm and not currently in a probing cycle
                if (tag_id in FIELD_MAP and 
                    dist is not None and 
                    dist <= 50.0 and 
                    not active_probing_lock and 
                    tag_id not in recently_probed_tags):
                    
                    recently_probed_tags.add(tag_id)
                    zone = FIELD_MAP[tag_id]
                    # Run the probe and LoRa transmission asynchronously
                    asyncio.create_task(execute_probe_and_lora_transmission(tag_id, zone["name"]))

            elif event == "qr_scanned":
                content = data.get("content")
                print(f"[WS TELEMETRY] QR Code Scanned: {content}")
                await manager.broadcast({
                    "event": "ack_qr",
                    "content": content,
                    "status": "Logged to database"
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WS Error]: {e}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)