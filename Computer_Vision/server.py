import asyncio
from datetime import datetime
import os
import random
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Rover Base Station Backend - AprilTag Vision")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Known field map: Mapping AprilTag IDs to farm locations
FIELD_MAP = {
    0: {"name": "Zone Alpha - Origin", "x": 0.0,  "y": 0.0},
    1: {"name": "Zone A - Bed 1",      "x": 5.0,  "y": 0.0},
    2: {"name": "Zone B - Bed 2",      "x": 10.0, "y": 2.5},
    3: {"name": "Zone C - Bed 3",      "x": 15.0, "y": -1.0},
}

LOG_FILE_CSV = "soil_probe_log.csv"
LOG_FILE_TXT = "soil_probe_log.txt"

# Initialize CSV log with header if not exists
if not os.path.exists(LOG_FILE_CSV):
    with open(LOG_FILE_CSV, "w") as f:
        f.write("Timestamp,Target_Type,AprilTag_ID,Zone_Name,Moisture_Pct,Temp_C,Temp_F,pH,LoRa_RSSI_dBm,LoRa_SNR_dB\n")

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

active_probing_lock = False
recently_probed_tags = set()

def append_to_log_files(entry: dict):
    """Appends probe instance to both CSV (for Excel) and human-readable TXT log."""
    with open(LOG_FILE_CSV, "a") as f:
        f.write(
            f"{entry['timestamp']},"
            f"{entry['target_type']},"
            f"{entry['tag_id']},"
            f"\"{entry['zone']}\","
            f"{entry['moisture_pct']},"
            f"{entry['temp_c']},"
            f"{entry['temp_f']},"
            f"{entry['ph']},"
            f"{entry['rssi']},"
            f"{entry['snr']}\n"
        )
    
    with open(LOG_FILE_TXT, "a") as f:
        f.write(
            f"[{entry['timestamp']}] AprilTag: ID {entry['tag_id']} | Location: {entry['zone']}\n"
            f"    └─ Moisture: {entry['moisture_pct']}% | Temp: {entry['temp_c']}°C ({entry['temp_f']}°F) | pH: {entry['ph']}\n"
            f"    └─ LoRa Telemetry: RSSI={entry['rssi']} dBm, SNR={entry['snr']} dB (Freq: 915.0 MHz)\n"
            f"{'-'*70}\n"
        )

async def execute_probe_and_lora(tag_id: int, zone_name: str, distance_cm: float):
    """Simulates mechanical soil probe actuation and LoRa RF transmission."""
    global active_probing_lock
    active_probing_lock = True
    
    print("\n" + "="*70)
    print(f"🚜 [ROVER] AprilTag ID {tag_id} Detected at {distance_cm:.1f} cm ({zone_name})")
    print("🚜 [ACTUATOR] Lowering mechanical soil probe into the dirt (sleep 1.2s)...")
    await asyncio.sleep(1.2)  # Simulate motor insertion delay
    
    print("🔬 [SENSORS] Sampling moisture, temperature, and soil pH (sleep 1.0s)...")
    await asyncio.sleep(1.0)  # Simulate sensor settling delay
    
    # Generate sensor values
    moisture_pct = round(random.uniform(19.0, 33.5), 1)
    temp_c = round(random.uniform(16.5, 23.8), 1)
    temp_f = round((temp_c * 9/5) + 32, 1)
    ph_level = round(random.uniform(6.35, 7.25), 2)
    
    # Generate LoRa RF parameters
    simulated_rssi = random.randint(-95, -65)
    simulated_snr = round(random.uniform(7.0, 10.5), 1)
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"    ├─ Soil Moisture:    {moisture_pct}%")
    print(f"    ├─ Soil Temp:        {temp_c}°C ({temp_f}°F)")
    print(f"    └─ Soil pH:          {ph_level}")

    print("🚜 [ACTUATOR] Retracting probe back into chassis...")
    print(f"📡 [LoRa TX] Broadcasting 915.0 MHz packet to Base Station...")
    
    log_entry = {
        "timestamp": timestamp_str,
        "target_type": "AprilTag",
        "tag_id": tag_id,
        "zone": zone_name,
        "moisture_pct": moisture_pct,
        "temp_c": temp_c,
        "temp_f": temp_f,
        "ph": ph_level,
        "rssi": simulated_rssi,
        "snr": simulated_snr
    }
    
    append_to_log_files(log_entry)
    print(f"💾 [LOG SAVED] Appended to '{LOG_FILE_CSV}' and '{LOG_FILE_TXT}'")
    print("="*70 + "\n")

    await manager.broadcast({
        "event": "probe_complete",
        "target_type": "AprilTag",
        "tag_id": tag_id,
        "zone": zone_name,
        "lora_meta": {
            "rssi": f"{simulated_rssi} dBm",
            "snr": f"{simulated_snr} dB",
            "frequency": "915.0 MHz"
        },
        "readings": {
            "moisture_pct": moisture_pct,
            "temperature_c": temp_c,
            "temperature_f": temp_f,
            "ph_level": ph_level
        },
        "timestamp": timestamp_str
    })

    # Cooldown before scanning the same tag again
    await asyncio.sleep(5.0)
    recently_probed_tags.discard(tag_id)
    active_probing_lock = False

@app.get("/")
async def serve_index():
    return FileResponse("index.html")

@app.get("/api/logs")
async def get_logs():
    if os.path.exists(LOG_FILE_TXT):
        with open(LOG_FILE_TXT, "r") as f:
            return {"logs": f.read()}
    return {"logs": "No probe records yet."}

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

                if (dist is not None and dist <= 85.0 and 
                    not active_probing_lock and 
                    tag_id not in recently_probed_tags):
                    
                    recently_probed_tags.add(tag_id)
                    zone_info = FIELD_MAP.get(tag_id, {"name": f"Station {tag_id}"})
                    asyncio.create_task(
                        execute_probe_and_lora(tag_id, zone_info["name"], dist)
                    )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WS Error]: {e}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)