from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
import models  # ensure models are registered
from routers import dashboard, students, shuttles, seats, trips, requests, vehicle_logs
from mqtt_client import start_mqtt_client
import mqtt_client

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="VIT Smart Shuttle API",
    description="Backend API for VIT Smart Shuttle System",
    version="1.0.0",
)

# CORS for Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include routers
app.include_router(dashboard.router)
app.include_router(students.router)
app.include_router(shuttles.router)
app.include_router(seats.router)
app.include_router(trips.router)
app.include_router(requests.router)
app.include_router(vehicle_logs.router)

@app.on_event('startup')
def startup_event():
    start_mqtt_client()

@app.get('/')
def root():
    return {"message": "VIT Smart Shuttle API is running", "docs": "/docs"}

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "VIT Smart Shuttle Backend",
        "mqtt": "connected" if mqtt_client.is_connected else "disconnected"
    }
