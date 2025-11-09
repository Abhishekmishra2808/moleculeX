"""
SSE (Server-Sent Events) Manager for real-time updates
Simpler and more reliable than WebSockets
"""
import asyncio
import json
from typing import Dict, List
from datetime import datetime
from collections import defaultdict


class SSEManager:
    """Manages Server-Sent Events connections for job updates"""
    
    def __init__(self):
        # job_id -> list of asyncio queues for each client
        self.active_connections: Dict[str, List[asyncio.Queue]] = defaultdict(list)
    
    def connect(self, job_id: str) -> asyncio.Queue:
        """Create a new SSE connection for a job"""
        queue = asyncio.Queue(maxsize=100)
        self.active_connections[job_id].append(queue)
        print(f"✅ SSE connected for job {job_id} (total: {len(self.active_connections[job_id])})")
        return queue
    
    def disconnect(self, job_id: str, queue: asyncio.Queue):
        """Remove an SSE connection"""
        if job_id in self.active_connections:
            try:
                self.active_connections[job_id].remove(queue)
                if not self.active_connections[job_id]:
                    del self.active_connections[job_id]
                print(f"✓ SSE disconnected for job {job_id}")
            except ValueError:
                pass
    
    async def send_update(self, job_id: str, event_type: str, data: dict):
        """Send update to all SSE connections for a job"""
        if job_id not in self.active_connections:
            return
        
        message = {
            "job_id": job_id,
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Send to all active connections for this job
        disconnected = []
        for queue in self.active_connections[job_id][:]:  # Copy to avoid modification during iteration
            try:
                # Non-blocking put
                if not queue.full():
                    await queue.put(message)
                else:
                    # Queue full, this connection is slow/dead
                    print(f"⚠️ SSE queue full for job {job_id}, disconnecting slow client")
                    disconnected.append(queue)
            except Exception as e:
                print(f"⚠️ Error sending SSE update: {e}")
                disconnected.append(queue)
        
        # Clean up disconnected clients
        for queue in disconnected:
            self.disconnect(job_id, queue)


# Global instance
sse_manager = SSEManager()
