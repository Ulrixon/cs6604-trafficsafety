"""
VCC API endpoints for real-time streaming and historical data collection.

Provides REST endpoints for:
- Starting/stopping real-time WebSocket streaming
- Historical data collection
- VCC data status and monitoring
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import datetime
from pydantic import BaseModel

from ..services.vcc_data_collection import collect_historical_vcc_data
from ..services.vcc_historical_processor import process_historical_vcc_data
from ..services.vcc_realtime_streaming import vcc_streamer
from ..services.vcc_realtime_processor import vcc_realtime_processor
from ..services.vcc_client import vcc_client
from ..core.config import settings


router = APIRouter(prefix="/vcc", tags=["VCC API"])


class HistoricalCollectionRequest(BaseModel):
    """Request model for historical data collection"""
    start_date: Optional[str] = None  # ISO format datetime
    end_date: Optional[str] = None  # ISO format datetime
    intersection_id: Optional[int] = None
    save_to_parquet: bool = True


class RealtimeStreamRequest(BaseModel):
    """Request model for starting real-time streaming"""
    intersection_id: str = "all"
    enable: bool = True


@router.get("/status")
def get_vcc_status():
    """
    Get VCC API connection status and configuration.
    
    Returns:
        Dictionary with VCC API status, configuration, and connection info
    """
    try:
        # Test authentication
        token = vcc_client.get_access_token()
        auth_status = "authenticated" if token else "failed"
        
        # Get MapData as connectivity test
        mapdata = vcc_client.get_mapdata(decoded=True)
        mapdata_count = len(mapdata) if mapdata else 0
        
        return {
            "status": "connected" if token else "disconnected",
            "authentication": auth_status,
            "base_url": settings.VCC_BASE_URL,
            "data_source": settings.DATA_SOURCE,
            "realtime_enabled": settings.REALTIME_ENABLED,
            "mapdata_available": mapdata_count,
            "streaming_active": vcc_streamer.running if hasattr(vcc_streamer, 'running') else False
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "base_url": settings.VCC_BASE_URL,
            "data_source": settings.DATA_SOURCE
        }


@router.post("/historical/collect")
def collect_historical_data(
    request: HistoricalCollectionRequest,
    background_tasks: BackgroundTasks
):
    """
    Collect historical data from VCC API.
    
    This endpoint starts background collection of historical data from VCC API.
    The data is collected, processed, and saved to Parquet storage.
    
    Args:
        request: Collection request with date range and options
        background_tasks: FastAPI background tasks
        
    Returns:
        Dictionary with collection status and job info
    """
    try:
        # Parse dates
        start_date = None
        if request.start_date:
            start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
        
        end_date = None
        if request.end_date:
            end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
        
        # Start background processing
        background_tasks.add_task(
            process_historical_vcc_data,
            start_date=start_date,
            end_date=end_date,
            intersection_id=request.intersection_id,
            save_to_parquet=request.save_to_parquet
        )
        
        return {
            "status": "started",
            "message": "Historical data collection started in background",
            "start_date": request.start_date,
            "end_date": request.end_date,
            "intersection_id": request.intersection_id,
            "save_to_parquet": request.save_to_parquet
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to start collection: {str(e)}")


@router.post("/historical/process")
def process_historical_data(
    request: HistoricalCollectionRequest,
    background_tasks: BackgroundTasks
):
    """
    Process collected historical data and compute safety indices.
    
    This endpoint processes already-collected data and computes safety indices.
    Use this after collecting data manually or if data is already available.
    
    Args:
        request: Processing request with date range and options
        background_tasks: FastAPI background tasks
        
    Returns:
        Dictionary with processing status
    """
    try:
        start_date = None
        if request.start_date:
            start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
        
        end_date = None
        if request.end_date:
            end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
        
        # Start background processing
        background_tasks.add_task(
            process_historical_vcc_data,
            start_date=start_date,
            end_date=end_date,
            intersection_id=request.intersection_id,
            save_to_parquet=request.save_to_parquet
        )
        
        return {
            "status": "started",
            "message": "Historical data processing started in background",
            "start_date": request.start_date,
            "end_date": request.end_date,
            "intersection_id": request.intersection_id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to start processing: {str(e)}")


@router.post("/realtime/start")
async def start_realtime_streaming(request: RealtimeStreamRequest):
    """
    Start real-time WebSocket streaming from VCC API.
    
    This endpoint starts streaming BSM and PSM messages in real-time.
    Messages are buffered in 1-minute intervals and safety indices are
    computed using 15-minute rolling windows.
    
    Args:
        request: Streaming request with intersection ID and enable flag
        
    Returns:
        Dictionary with streaming status
    """
    if not settings.REALTIME_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Real-time streaming is disabled. Set REALTIME_ENABLED=true to enable."
        )
    
    if vcc_streamer.running:
        return {
            "status": "already_running",
            "message": "Real-time streaming is already active"
        }
    
    # Initialize processor with MapData
    try:
        mapdata_list = vcc_client.get_mapdata(decoded=True)
        vcc_realtime_processor.set_mapdata(mapdata_list)
    except Exception as e:
        print(f"⚠ Warning: Failed to load MapData: {e}")
    
    # Define callback for processing 1-minute intervals
    async def process_interval(bsm_messages, psm_messages, interval_start):
        """Callback to process 1-minute interval of messages"""
        try:
            result = await vcc_realtime_processor.process_minute_interval(
                bsm_messages,
                psm_messages,
                interval_start
            )
            return result
        except Exception as e:
            print(f"⚠ Error processing interval: {e}")
            return None
    
    # Start streaming
    try:
        # Note: This will run indefinitely until stopped
        # In production, you may want to run this in a background task or separate process
        import asyncio
        asyncio.create_task(
            vcc_streamer.start_streaming(
                callback=process_interval,
                intersection_id=request.intersection_id
            )
        )
        
        return {
            "status": "started",
            "message": "Real-time streaming started",
            "intersection_id": request.intersection_id,
            "interval_minutes": 1,
            "window_minutes": 15
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start streaming: {str(e)}")


@router.post("/realtime/stop")
async def stop_realtime_streaming():
    """
    Stop real-time WebSocket streaming.
    
    Returns:
        Dictionary with streaming status
    """
    if not vcc_streamer.running:
        return {
            "status": "not_running",
            "message": "Real-time streaming is not active"
        }
    
    try:
        await vcc_streamer.stop_streaming()
        return {
            "status": "stopped",
            "message": "Real-time streaming stopped"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop streaming: {str(e)}")


@router.get("/realtime/status")
def get_realtime_status():
    """
    Get real-time streaming status.
    
    Returns:
        Dictionary with streaming status and statistics
    """
    return {
        "running": vcc_streamer.running if hasattr(vcc_streamer, 'running') else False,
        "buffer_size_bsm": len(vcc_streamer.bsm_buffer) if hasattr(vcc_streamer, 'bsm_buffer') else 0,
        "buffer_size_psm": len(vcc_streamer.psm_buffer) if hasattr(vcc_streamer, 'psm_buffer') else 0,
        "current_interval_start": vcc_streamer.current_interval_start.isoformat() if (
            hasattr(vcc_streamer, 'current_interval_start') and 
            vcc_streamer.current_interval_start
        ) else None,
        "window_size": len(vcc_realtime_processor.feature_window) if hasattr(vcc_realtime_processor, 'feature_window') else 0,
        "window_capacity": vcc_realtime_processor.window_minutes if hasattr(vcc_realtime_processor, 'window_minutes') else 0
    }


@router.get("/mapdata")
def get_mapdata(intersection_id: Optional[int] = None):
    """
    Get MapData messages from VCC API.
    
    Args:
        intersection_id: Optional intersection ID filter
        
    Returns:
        List of MapData messages
    """
    try:
        mapdata = vcc_client.get_mapdata(intersection_id=intersection_id, decoded=True)
        return {
            "status": "success",
            "count": len(mapdata),
            "mapdata": mapdata
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get MapData: {str(e)}")


@router.get("/test/connection")
def test_connection():
    """
    Test VCC API connection and authentication.
    
    Returns:
        Dictionary with connection test results
    """
    try:
        # Test authentication
        token = vcc_client.get_access_token()
        if not token:
            return {
                "status": "failed",
                "message": "Failed to obtain access token",
                "authenticated": False
            }
        
        # Test API endpoints
        bsm = vcc_client.get_bsm_current()
        psm = vcc_client.get_psm_current()
        mapdata = vcc_client.get_mapdata(decoded=True)
        
        return {
            "status": "success",
            "authenticated": True,
            "endpoints": {
                "bsm": {
                    "available": True,
                    "message_count": len(bsm) if bsm else 0
                },
                "psm": {
                    "available": True,
                    "message_count": len(psm) if psm else 0
                },
                "mapdata": {
                    "available": True,
                    "message_count": len(mapdata) if mapdata else 0
                }
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "authenticated": False
        }

