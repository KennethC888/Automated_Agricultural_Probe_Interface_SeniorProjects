import asyncio
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Rover Base Station Backend")

# Enable CORS for local testing across ports
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
    event_type: str  # "apriltag_detected" or "qr_scanned"
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

# ------------------------------------------------------------------
# Static HTML Route
# ------------------------------------------------------------------
@app.get("/")
async def serve_index():
    """Serves the frontend index.html directly from the backend."""
    return FileResponse("index.html")

# ------------------------------------------------------------------
# REST Endpoints (for standard HTTP requests)
# ------------------------------------------------------------------
@app.get("/api/field-map")
async def get_field_map():
    return {"status": "ok", "map": FIELD_MAP}

@app.post("/api/telemetry")
async def receive_telemetry(payload: TelemetryPayload):
    print(f"\n[HTTP REST] Received {payload.event_type} event: {payload.dict()}")
    return {"status": "received", "timestamp": datetime.utcnow().isoformat()}

# ------------------------------------------------------------------
# WebSocket Endpoint (for continuous real-time bi-directional streaming)
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
                
                print(f"[WS TELEMETRY] AprilTag ID: {tag_id} | Dist: {dist}cm | Heading: {heading}°")

                # If the tag matches a known probe point and the rover is close enough:
                if tag_id in FIELD_MAP and dist is not None and dist <= 50.0:
                    zone = FIELD_MAP[tag_id]
                    print(f"--> [BASE STATION] TRIGGERING SOIL PROBE at {zone['name']}!")
                    
                    # Simulate soil sensor cycle
                    await asyncio.sleep(0.5)
                    soil_reading = {
                        "moisture_pct": 28.4,
                        "ph_level": 6.8,
                        "nitrogen_ppm": 42
                    }

                    # Notify frontend/base station that probe cycle completed
                    await manager.broadcast({
                        "event": "probe_complete",
                        "tag_id": tag_id,
                        "zone": zone["name"],
                        "readings": soil_reading,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    })

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
    # Runs the local development server on port 8000
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)