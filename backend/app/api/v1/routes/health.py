"""Health check routes."""
from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/status")
async def status():
    """Get system status."""
    return {"status": "operational", "component": "api"}
