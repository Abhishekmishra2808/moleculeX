"""
MoleculeX - AI-Driven Pharmaceutical Insight Discovery Platform
Main FastAPI Application
"""
# Suppress Pydantic warnings from google-genai SDK
import warnings
warnings.filterwarnings("ignore", message=".*shadows an attribute in parent.*", category=UserWarning)

from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
import asyncio
import json
import os

from routes import query_router, status_router
from sse_manager import sse_manager

# Create necessary directories
os.makedirs("data/jobs", exist_ok=True)
os.makedirs("data/reports", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    print("🚀 MoleculeX is starting up...")
    yield
    print("👋 MoleculeX is shutting down...")


app = FastAPI(
    title="MoleculeX API",
    description="AI-Driven Pharmaceutical Insight Discovery Platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for React frontend
# Get allowed origins from environment variable or use defaults
allowed_origins = os.getenv("FRONTEND_URL", "http://localhost:5173").split(",")
# Add production and development origins
allowed_origins.extend([
    "http://localhost:5173", 
    "http://localhost:3000",
    "https://molecule-x.vercel.app",
    "https://molecule-x.vercel.app/"
])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(query_router, prefix="/api", tags=["queries"])
app.include_router(status_router, prefix="/api", tags=["status"])


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "MoleculeX API",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development")
    }


@app.get("/api/health")
async def health_check():
    """Detailed health check for monitoring"""
    return {
        "status": "ok",
        "service": "MoleculeX API",
        "version": "1.0.0",
        "checks": {
            "api": "healthy",
            "websocket": "healthy"
        }
    }


@app.get("/api/stream/{job_id}")
async def sse_endpoint(job_id: str, request: Request):
    """Server-Sent Events endpoint for real-time job updates"""
    
    async def event_generator():
        queue = sse_manager.connect(job_id)
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    print(f"✓ Client disconnected from SSE stream for job {job_id}")
                    break
                
                try:
                    # Wait for message with timeout
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    # Format as SSE
                    event_data = json.dumps(message)
                    yield f"data: {event_data}\n\n"
                    
                    # If job completed or failed, wait longer for client to fetch and render results
                    if message.get("event_type") in ["job_completed", "job_failed"]:
                        print(f"✓ Job {message.get('event_type')} for {job_id}, keeping stream open for 10s...")
                        # Send keepalive while waiting
                        for i in range(10):
                            await asyncio.sleep(1)
                            yield ": keepalive\n\n"
                        print(f"✓ Closing SSE stream for {job_id}")
                        break
                        
                except asyncio.TimeoutError:
                    # Send keepalive comment to prevent timeout
                    yield ": keepalive\n\n"
                    
        except Exception as e:
            print(f"⚠️ SSE error for job {job_id}: {e}")
        finally:
            sse_manager.disconnect(job_id, queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering in nginx
        }
    )


@app.get("/api/reports/{filename}")
async def get_report(filename: str):
    """Serve generated reports (PDF or text). Looks in project_root/data/reports and backend/data/reports."""
    # Determine probable locations
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(backend_dir)
    candidates = [
        os.path.join(project_root, "data", "reports", filename),
        os.path.join("data", "reports", filename),
        os.path.join(backend_dir, "data", "reports", filename),
    ]
    file_path = next((p for p in candidates if os.path.exists(p)), None)
    if not file_path:
        raise HTTPException(status_code=404, detail="Report not found")
    # Infer media type from extension
    ext = os.path.splitext(file_path)[1].lower()
    media_type = "application/pdf" if ext == ".pdf" else "text/plain"
    return FileResponse(file_path, media_type=media_type, filename=filename)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        timeout_keep_alive=120,  # Keep connections alive for 2 minutes
        ws_ping_interval=20,      # Ping every 20 seconds
        ws_ping_timeout=20        # Wait 20s for pong response
    )
