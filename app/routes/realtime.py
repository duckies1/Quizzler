from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from typing import Optional
import json
import logging
from app.utils.websocket_manager import connection_manager
from app.utils.auth_utils import get_current_user_from_token
from app.models.realtime import game_storage

router = APIRouter()
security = HTTPBearer(auto_error=False)

logger = logging.getLogger(__name__)

async def get_user_from_websocket_token(token: Optional[str] = None) -> Optional[dict]:
    """Extract user from WebSocket token parameter"""
    if not token:
        return None
    try:
        if token.startswith('Bearer '):
            token = token[7:]
        
        user = await get_current_user_from_token(token)
        return user
    except Exception as e:
        logger.error(f"Error extracting user from token: {e}")
        return None

@router.websocket("/ws/host/{room_code}")
async def websocket_host_endpoint(websocket: WebSocket, room_code: str, token: Optional[str] = None):
    """WebSocket endpoint for quiz hosts (authenticated)"""
    
    user = await get_user_from_websocket_token(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
        return
    
    host_id = user.get("id")
    if not host_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid user")
        return
    
    existing_session = game_storage.get_session(room_code)
    if existing_session and existing_session.host_id != host_id:
        await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA, reason="Room code already in use")
        return
    
    actual_room_code = await connection_manager.connect_host(websocket, host_id)
    if not actual_room_code:
        return
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await connection_manager.handle_host_message(actual_room_code, message)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON from host in room {actual_room_code}")
                await connection_manager.send_error(websocket, "Invalid message format")
            except Exception as e:
                logger.error(f"Error processing host message: {e}")
                await connection_manager.send_error(websocket, f"Error processing message: {str(e)}")
    
    except WebSocketDisconnect:
        logger.info(f"Host disconnected from room {actual_room_code}")
        await connection_manager.disconnect_host(actual_room_code)
    except Exception as e:
        logger.error(f"Unexpected error in host websocket: {e}")
        await connection_manager.disconnect_host(actual_room_code)

@router.websocket("/ws/player/{room_code}")
async def websocket_player_endpoint(websocket: WebSocket, room_code: str, username: str):
    """WebSocket endpoint for players (no authentication required)"""
    
    if not username or len(username.strip()) < 1:
        await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA, reason="Username required")
        return
    
    if len(username.strip()) > 20:
        await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA, reason="Username too long")
        return
    
    username = username.strip()
    
    player_id = await connection_manager.connect_player(websocket, room_code, username)
    if not player_id:
        return
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await connection_manager.handle_player_message(room_code, player_id, message)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON from player {player_id} in room {room_code}")
                await connection_manager.send_error(websocket, "Invalid message format")
            except Exception as e:
                logger.error(f"Error processing player message: {e}")
                await connection_manager.send_error(websocket, f"Error processing message: {str(e)}")
    
    except WebSocketDisconnect:
        logger.info(f"Player {player_id} disconnected from room {room_code}")
        await connection_manager.disconnect_player(room_code, player_id)
    except Exception as e:
        logger.error(f"Unexpected error in player websocket: {e}")
        await connection_manager.disconnect_player(room_code, player_id)

@router.get("/rooms/{room_code}/info")
async def get_room_info(room_code: str):
    """Get basic room information (for validation)"""
    session = game_storage.get_session(room_code)
    if not session or not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found or inactive"
        )
    
    return {
        "room_code": room_code,
        "is_active": session.is_active,
        "player_count": session.get_player_count(),
        "has_current_question": session.current_question is not None,
        "created_at": session.created_at
    }

@router.get("/rooms/validate/{room_code}")
async def validate_room_code(room_code: str):
    """Validate if room code exists and is active"""
    session = game_storage.get_session(room_code)
    
    return {
        "valid": session is not None and session.is_active,
        "room_code": room_code,
        "player_count": session.get_player_count() if session else 0
    }

@router.post("/cleanup-sessions")
async def cleanup_inactive_sessions():
    """Manual cleanup of inactive sessions (for admin/maintenance)"""
    try:
        initial_count = len(game_storage.sessions)
        game_storage.cleanup_inactive_sessions(max_age_hours=2)
        final_count = len(game_storage.sessions)
        
        return {
            "message": "Cleanup completed",
            "removed_sessions": initial_count - final_count,
            "active_sessions": final_count
        }
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cleanup failed: {str(e)}"
        )

@router.get("/stats")
async def get_realtime_stats():
    """Get statistics about active sessions"""
    try:
        sessions = game_storage.sessions
        total_sessions = len(sessions)
        active_sessions = sum(1 for session in sessions.values() if session.is_active)
        total_players = sum(session.get_player_count() for session in sessions.values())
        
        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "total_connected_players": total_players,
            "rooms": [
                {
                    "room_code": room_code,
                    "is_active": session.is_active,
                    "player_count": session.get_player_count(),
                    "has_question": session.current_question is not None,
                    "created_at": session.created_at
                }
                for room_code, session in sessions.items()
            ]
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )

@router.get("/health")
async def health_check():
    """Health check endpoint for monitoring system status"""
    try:
        health_status = connection_manager.get_health_status()
        memory_stats = game_storage.get_memory_stats()
        
        # Combine health data
        health_data = {
            **health_status,
            "memory_stats": memory_stats,
            "timestamp": game_storage.sessions.get("_last_cleanup", 0) if hasattr(game_storage, "sessions") else 0
        }
        
        # Determine overall health
        if health_data["status"] == "error":
            raise HTTPException(status_code=503, detail=health_data)
        elif health_data["status"] == "warning":
            return {"warning": True, **health_data}
        else:
            return {"healthy": True, **health_data}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={"status": "error", "message": f"Health check failed: {str(e)}"}
        )

@router.post("/admin/cleanup")
async def force_cleanup():
    """Force cleanup of inactive sessions (admin endpoint)"""
    try:
        removed_count = game_storage.cleanup_inactive_sessions(max_age_hours=1)  # More aggressive cleanup
        await connection_manager.cleanup_stale_sessions()
        
        return {
            "message": "Cleanup completed successfully",
            "removed_sessions": removed_count,
            "remaining_sessions": len(game_storage.sessions)
        }
    except Exception as e:
        logger.error(f"Force cleanup failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Cleanup failed: {str(e)}"
        )
