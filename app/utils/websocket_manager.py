import asyncio
import json
import secrets
import string
import time
from collections import defaultdict, deque
from typing import Dict, Set, Optional, Tuple
from fastapi import WebSocket, WebSocketDisconnect, HTTPException
import logging
from app.models.realtime import (
    GameSession, Player, Question, MessageType, BaseMessage,
    CreateRoomMessage, RoomCreatedMessage, NewQuestionMessage, CloseRoomMessage,
    JoinRoomMessage, PlayerJoinedMessage, AnswerMessage,
    QuestionMessage, QuestionEndedMessage, ResultsMessage, RoomClosedMessage,
    ErrorMessage, PlayerCountMessage, AnswerCountMessage,
    game_storage
)

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Track active connections
        self.host_connections: Dict[str, WebSocket] = {}  # room_code -> host_ws
        self.player_connections: Dict[str, Dict[str, WebSocket]] = {}  # room_code -> player_id -> ws
        
        # Connection limits and rate limiting
        self.MAX_PLAYERS_PER_ROOM = 50  # Max players per room
        self.MAX_ROOMS = 100  # Max concurrent rooms
        self.MAX_CONNECTIONS_PER_IP = 100  # Max connections per IP
        self.RATE_LIMIT_WINDOW = 60  # Rate limit window in seconds
        self.MAX_REQUESTS_PER_WINDOW = 30  # Max requests per window
        
        # Rate limiting tracking
        self.connection_attempts: Dict[str, deque] = defaultdict(deque)  # IP -> timestamps
        self.ip_connections: Dict[str, int] = defaultdict(int)  # IP -> connection count
        
        # Performance monitoring
        self.metrics = {
            'total_connections': 0,
            'active_rooms': 0,
            'messages_sent': 0,
            'errors': 0,
            'disconnections': 0,
            'questions_processed': 0,
            'answers_processed': 0,
            'memory_usage_mb': 0
        }
        
        # Background tasks
        self.cleanup_task = None
        self.heartbeat_task = None
        self.start_background_tasks()
        
        # Heartbeat settings
        self.HEARTBEAT_INTERVAL = 30  # Send ping every 30 seconds
        self.HEARTBEAT_TIMEOUT = 60   # Consider connection dead after 60 seconds
    
    def start_background_tasks(self):
        """Start background tasks"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            
        self.cleanup_task = asyncio.create_task(self.periodic_cleanup())
        self.heartbeat_task = asyncio.create_task(self.heartbeat_monitor())
    
    async def periodic_cleanup(self):
        """Periodic cleanup of inactive sessions and stale connections"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                await self.cleanup_stale_sessions()
                await self.cleanup_rate_limits()
                self.log_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
    
    async def heartbeat_monitor(self):
        """Monitor connection health with heartbeat"""
        while True:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                await self.send_heartbeats()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {e}")
    
    async def send_heartbeats(self):
        """Send heartbeat messages to all active connections"""
        dead_hosts = []
        dead_players = []
        
        heartbeat_message = json.dumps({
            "type": "heartbeat",
            "timestamp": time.time()
        })
        
        # Check host connections
        for room_code, websocket in list(self.host_connections.items()):
            try:
                # Send heartbeat message instead of ping
                await websocket.send_text(heartbeat_message)
            except Exception as e:
                logger.warning(f"Host heartbeat failed for room {room_code}: {e}")
                dead_hosts.append(room_code)
        
        # Check player connections
        for room_code, players in list(self.player_connections.items()):
            for player_id, websocket in list(players.items()):
                try:
                    # Send heartbeat message instead of ping
                    await websocket.send_text(heartbeat_message)
                except Exception as e:
                    logger.warning(f"Player heartbeat failed for {player_id} in room {room_code}: {e}")
                    dead_players.append((room_code, player_id))
        
        # Clean up dead connections
        for room_code in dead_hosts:
            await self.disconnect_host(room_code)
        
        for room_code, player_id in dead_players:
            await self.disconnect_player(room_code, player_id)
    
    async def cleanup_stale_sessions(self):
        """Clean up stale sessions and connections"""
        current_time = time.time()
        stale_rooms = []
        
        for room_code, session in game_storage.sessions.items():
            # Remove sessions older than 2 hours or with no active players
            if (not session.is_active or 
                (current_time - session.created_at) > 7200 or  # 2 hours
                session.get_player_count() == 0):
                
                stale_rooms.append(room_code)
        
        for room_code in stale_rooms:
            await self.cleanup_room(room_code)
            logger.info(f"Cleaned up stale room: {room_code}")
    
    async def cleanup_rate_limits(self):
        """Clean up old rate limit entries"""
        current_time = time.time()
        cutoff_time = current_time - self.RATE_LIMIT_WINDOW
        
        for ip, timestamps in list(self.connection_attempts.items()):
            # Remove old timestamps
            while timestamps and timestamps[0] < cutoff_time:
                timestamps.popleft()
            
            # Remove empty entries
            if not timestamps:
                del self.connection_attempts[ip]
    
    def log_metrics(self):
        """Log current performance metrics with memory usage"""
        import psutil
        import os
        
        try:
            # Update metrics
            self.metrics['active_rooms'] = len(game_storage.sessions)
            
            # Calculate memory usage
            process = psutil.Process(os.getpid())
            self.metrics['memory_usage_mb'] = round(process.memory_info().rss / 1024 / 1024, 2)
            
            # Calculate total players
            total_players = sum(session.get_player_count() for session in game_storage.sessions.values())
            
            logger.info(f"Performance Metrics: Rooms={self.metrics['active_rooms']}, "
                       f"Players={total_players}, Memory={self.metrics['memory_usage_mb']}MB, "
                       f"Messages={self.metrics['messages_sent']}, Errors={self.metrics['errors']}")
            
        except Exception as e:
            logger.error(f"Error logging metrics: {e}")
    
    def get_health_status(self) -> dict:
        """Get current system health status"""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
            
            total_players = sum(session.get_player_count() for session in game_storage.sessions.values())
            
            return {
                "status": "healthy" if memory_mb < 1000 and len(game_storage.sessions) < self.MAX_ROOMS else "warning",
                "active_rooms": len(game_storage.sessions),
                "total_players": total_players,
                "memory_usage_mb": round(memory_mb, 2),
                "cpu_percent": cpu_percent,
                "metrics": self.metrics,
                "limits": {
                    "max_rooms": self.MAX_ROOMS,
                    "max_players_per_room": self.MAX_PLAYERS_PER_ROOM,
                    "max_connections_per_ip": self.MAX_CONNECTIONS_PER_IP
                }
            }
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return {"status": "error", "message": str(e)}
    
    def check_rate_limit(self, client_ip: str) -> bool:
        """Check if client IP is within rate limits"""
        current_time = time.time()
        cutoff_time = current_time - self.RATE_LIMIT_WINDOW
        
        # Clean old entries for this IP
        timestamps = self.connection_attempts[client_ip]
        while timestamps and timestamps[0] < cutoff_time:
            timestamps.popleft()
        
        # Check rate limit
        if len(timestamps) >= self.MAX_REQUESTS_PER_WINDOW:
            return False
        
        # Add current timestamp
        timestamps.append(current_time)
        return True
    
    def check_connection_limits(self, room_code: str = None, client_ip: str = None) -> Tuple[bool, str]:
        """Check various connection limits"""
        # Check max rooms limit
        if len(game_storage.sessions) >= self.MAX_ROOMS:
            return False, "Maximum number of rooms reached"
        
        # Check per-IP connection limit
        if client_ip and self.ip_connections[client_ip] >= self.MAX_CONNECTIONS_PER_IP:
            return False, "Too many connections from your IP address"
        
        # Check players per room limit
        if room_code:
            session = game_storage.get_session(room_code)
            if session and session.get_player_count() >= self.MAX_PLAYERS_PER_ROOM:
                return False, f"Room is full (max {self.MAX_PLAYERS_PER_ROOM} players)"
        
        return True, ""
    
    def generate_room_code(self, length: int = 8) -> str:
        """Generate unique alphanumeric room code"""
        attempts = 0
        max_attempts = 100
        
        while attempts < max_attempts:
            # Generate random alphanumeric string
            chars = string.ascii_uppercase + string.digits
            room_code = ''.join(secrets.choice(chars) for _ in range(length))
            
            # Ensure uniqueness
            if room_code not in game_storage.sessions:
                return room_code
            
            attempts += 1
        
        raise Exception("Failed to generate unique room code")
    
    async def connect_host(self, websocket: WebSocket, host_id: str, client_ip: str = None) -> Optional[str]:
        """Connect host and create a new room"""
        try:
            # Check rate limits and connection limits
            if client_ip:
                if not self.check_rate_limit(client_ip):
                    await websocket.close(code=1008, reason="Rate limit exceeded")
                    self.metrics['errors'] += 1
                    return None
                
                can_connect, error_msg = self.check_connection_limits(client_ip=client_ip)
                if not can_connect:
                    await websocket.close(code=1008, reason=error_msg)
                    self.metrics['errors'] += 1
                    return None
            
            await websocket.accept()
            
            # Generate unique room code
            room_code = self.generate_room_code()
            
            # Create game session
            session = game_storage.create_session(room_code, host_id, websocket)
            
            # Track host connection
            self.host_connections[room_code] = websocket
            self.player_connections[room_code] = {}
            
            # Update metrics and IP tracking
            self.metrics['total_connections'] += 1
            if client_ip:
                self.ip_connections[client_ip] += 1
            
            # Send room created message to host
            await self.send_to_host(room_code, RoomCreatedMessage(room_code=room_code))
            
            logger.info(f"Host {host_id} created room {room_code}")
            return room_code
            
        except Exception as e:
            logger.error(f"Error connecting host: {e}")
            self.metrics['errors'] += 1
            try:
                await self.send_error(websocket, f"Failed to create room: {str(e)}")
            except:
                pass
            return None
    
    async def connect_player(self, websocket: WebSocket, room_code: str, username: str, client_ip: str = None) -> Optional[str]:
        """Connect player to existing room"""
        try:
            # Check rate limits and connection limits
            if client_ip:
                if not self.check_rate_limit(client_ip):
                    await websocket.close(code=1008, reason="Rate limit exceeded")
                    self.metrics['errors'] += 1
                    return None
                
                can_connect, error_msg = self.check_connection_limits(room_code=room_code, client_ip=client_ip)
                if not can_connect:
                    await websocket.close(code=1008, reason=error_msg)
                    self.metrics['errors'] += 1
                    return None
            
            await websocket.accept()
            
            # Check if room exists
            session = game_storage.get_session(room_code)
            if not session or not session.is_active:
                await self.send_error(websocket, "Room doesn't exist or is no longer active")
                return None
            
            # Generate unique player ID with collision detection
            max_attempts = 10
            player_id = None
            for attempt in range(max_attempts):
                temp_id = f"{room_code}_{username}_{secrets.token_hex(4)}"
                if temp_id not in session.players:
                    player_id = temp_id
                    break
            
            if not player_id:
                await self.send_error(websocket, "Failed to generate unique player ID")
                return None
            
            # Create player
            player = Player(id=player_id, username=username, ws=websocket)
            session.players[player_id] = player
            
            # Track player connection
            if room_code not in self.player_connections:
                self.player_connections[room_code] = {}
            self.player_connections[room_code][player_id] = websocket
            
            # Update metrics and IP tracking
            self.metrics['total_connections'] += 1
            if client_ip:
                self.ip_connections[client_ip] += 1
            
            # Broadcast to other players (not host) that new player joined
            await self.broadcast_to_players(
                room_code, 
                PlayerJoinedMessage(username=username, player_count=session.get_player_count()),
                exclude_player=player_id
            )
            
            # Send player count update to host
            await self.send_to_host(room_code, PlayerCountMessage(count=session.get_player_count()))
            
            logger.info(f"Player {username} joined room {room_code} ({session.get_player_count()}/{self.MAX_PLAYERS_PER_ROOM})")
            return player_id
            
        except Exception as e:
            logger.error(f"Error connecting player: {e}")
            self.metrics['errors'] += 1
            try:
                await self.send_error(websocket, f"Failed to join room: {str(e)}")
            except:
                pass
            return None
    
    async def disconnect_host(self, room_code: str, client_ip: str = None):
        """Handle host disconnection"""
        try:
            session = game_storage.get_session(room_code)
            if session:
                # Mark session as inactive
                session.is_active = False
                
                # Notify all players that room is closed
                await self.broadcast_to_players(
                    room_code, 
                    RoomClosedMessage(reason="Host disconnected")
                )
                
                # Close all player connections
                await self.close_all_player_connections(room_code)
                
                # Clean up room
                await self.cleanup_room(room_code)
                
                # Update metrics
                self.metrics['disconnections'] += 1
                if client_ip:
                    self.ip_connections[client_ip] = max(0, self.ip_connections[client_ip] - 1)
                
                logger.info(f"Room {room_code} closed due to host disconnect")
                
        except Exception as e:
            logger.error(f"Error disconnecting host: {e}")
            self.metrics['errors'] += 1
    
    async def disconnect_player(self, room_code: str, player_id: str, client_ip: str = None):
        """Handle player disconnection"""
        try:
            session = game_storage.get_session(room_code)
            if session and player_id in session.players:
                # Mark player as disconnected
                session.players[player_id].connected = False
                
                # Remove from connection tracking
                if room_code in self.player_connections and player_id in self.player_connections[room_code]:
                    del self.player_connections[room_code][player_id]
                
                # Update host with new player count
                await self.send_to_host(room_code, PlayerCountMessage(count=session.get_player_count()))
                
                # Update metrics
                self.metrics['disconnections'] += 1
                if client_ip:
                    self.ip_connections[client_ip] = max(0, self.ip_connections[client_ip] - 1)
                
                # Clean up disconnected player after delay (they might reconnect)
                asyncio.create_task(self.delayed_player_cleanup(room_code, player_id))
                
                logger.info(f"Player {player_id} disconnected from room {room_code}")
                
        except Exception as e:
            logger.error(f"Error disconnecting player: {e}")
            self.metrics['errors'] += 1
    
    async def delayed_player_cleanup(self, room_code: str, player_id: str, delay: int = 60):
        """Clean up disconnected player after delay"""
        await asyncio.sleep(delay)
        
        try:
            session = game_storage.get_session(room_code)
            if session and player_id in session.players:
                player = session.players[player_id]
                if not player.connected:
                    # Remove player if still disconnected
                    del session.players[player_id]
                    
                    # Update host with new player count
                    await self.send_to_host(room_code, PlayerCountMessage(count=session.get_player_count()))
                    
                    logger.info(f"Cleaned up disconnected player {player_id} from room {room_code}")
        except Exception as e:
            logger.error(f"Error in delayed player cleanup: {e}")
    
    async def cleanup_room(self, room_code: str):
        """Clean up all room resources"""
        try:
            # Close all player connections
            await self.close_all_player_connections(room_code)
            
            # Remove from connection tracking
            if room_code in self.host_connections:
                del self.host_connections[room_code]
            if room_code in self.player_connections:
                del self.player_connections[room_code]
            
            # Remove session
            game_storage.remove_session(room_code)
            
        except Exception as e:
            logger.error(f"Error cleaning up room {room_code}: {e}")
    
    async def handle_host_message(self, room_code: str, message: dict):
        """Handle messages from host"""
        try:
            message_type = message.get("type")
            session = game_storage.get_session(room_code)
            
            if not session:
                return
            
            if message_type == MessageType.NEW_QUESTION:
                await self.handle_new_question(room_code, message)
            elif message_type == MessageType.CLOSE_ROOM:
                await self.handle_close_room(room_code)
            else:
                logger.warning(f"Unknown host message type: {message_type}")
                
        except Exception as e:
            logger.error(f"Error handling host message: {e}")
            await self.send_to_host(room_code, ErrorMessage(message=f"Error processing message: {str(e)}"))
    
    async def handle_player_message(self, room_code: str, player_id: str, message: dict):
        """Handle messages from player"""
        try:
            message_type = message.get("type")
            session = game_storage.get_session(room_code)
            
            if not session:
                return
            
            if message_type == MessageType.ANSWER:
                await self.handle_player_answer(room_code, player_id, message)
            else:
                logger.warning(f"Unknown player message type: {message_type}")
                
        except Exception as e:
            logger.error(f"Error handling player message: {e}")
            if room_code in self.player_connections and player_id in self.player_connections[room_code]:
                websocket = self.player_connections[room_code][player_id]
                await self.send_error(websocket, f"Error processing message: {str(e)}")
    
    async def handle_new_question(self, room_code: str, message: dict):
        """Handle new question from host with optimized broadcasting"""
        try:
            session = game_storage.get_session(room_code)
            if not session:
                return
            
            # Create question object
            question_data = NewQuestionMessage(**message)
            question = Question(
                text=question_data.question,
                options=question_data.options,
                correct_answer=question_data.correct_answer,
                time_limit=question_data.time_limit or session.quiz_config["question_time_limit"],
                start_time=question_data.timestamp
            )
            
            # Clear previous question and set new one
            session.current_question = question
            
            # Reset player answers efficiently
            await self._reset_player_states(session)
            
            # Broadcast question to all players (without correct answer)
            player_message = QuestionMessage(
                question=question.text,
                options=question.options,
                time_limit=question.time_limit,
                question_start_time=question.start_time
            )
            
            # Broadcast with retry for better reliability
            successful_sends = await self.broadcast_to_players(room_code, player_message, retries=2)
            
            # Start answer collection timer
            asyncio.create_task(self.question_timer(room_code, question.time_limit))
            
            logger.info(f"New question sent to room {room_code}, reached {successful_sends} players")
            
        except Exception as e:
            logger.error(f"Error handling new question: {e}")
            self.metrics['errors'] += 1
            await self.send_to_host(room_code, ErrorMessage(message=f"Error sending question: {str(e)}"))
    
    async def _reset_player_states(self, session: GameSession):
        """Efficiently reset player answer states"""
        try:
            for player in session.players.values():
                if player.connected:
                    player.current_answer = None
                    player.answer_time = None
        except Exception as e:
            logger.error(f"Error resetting player states: {e}")
    
    async def handle_player_answer(self, room_code: str, player_id: str, message: dict):
        """Handle answer from player with optimized processing"""
        try:
            session = game_storage.get_session(room_code)
            if not session or not session.current_question:
                return
            
            # Check if player already answered (double-click protection)
            if player_id in session.current_question.answers:
                return
            
            answer_data = AnswerMessage(**message)
            
            # Atomic answer recording
            session.current_question.answers[player_id] = {
                "option": answer_data.option,
                "timestamp": answer_data.timestamp
            }
            
            # Update player's current answer
            if player_id in session.players:
                player = session.players[player_id]
                player.current_answer = answer_data.option
                player.answer_time = answer_data.timestamp
            
            # Get counts efficiently
            answer_count = len(session.current_question.answers)
            total_players = session.get_player_count()
            
            # Send answer count update to host (batch updates every few answers)
            if answer_count == 1 or answer_count % 5 == 0 or answer_count >= total_players:
                await self.send_to_host(
                    room_code, 
                    AnswerCountMessage(answered=answer_count, total=total_players)
                )
            
            # If all players answered, end question early
            if answer_count >= total_players and total_players > 0:
                # Cancel the timer task if it exists
                await self.end_question(room_code)
            
        except Exception as e:
            logger.error(f"Error handling player answer: {e}")
            self.metrics['errors'] += 1
    
    async def question_timer(self, room_code: str, time_limit: int):
        """Timer for question duration"""
        await asyncio.sleep(time_limit)
        await self.end_question(room_code)
    
    async def end_question(self, room_code: str):
        """End current question and send results"""
        try:
            session = game_storage.get_session(room_code)
            if not session or not session.current_question:
                return
            
            question = session.current_question
            
            # Calculate results
            results = session.calculate_scores()
            total_answers = len(question.answers)
            correct_answers = sum(1 for ans in question.answers.values() 
                                if ans["option"] == question.correct_answer)
            
            # Send results to host
            await self.send_to_host(
                room_code,
                ResultsMessage(
                    top_5=results,
                    total_answers=total_answers,
                    correct_answers=correct_answers
                )
            )
            
            # Send correct answer to all players
            await self.broadcast_to_players(
                room_code,
                QuestionEndedMessage(correct_answer=question.correct_answer)
            )
            
            # Clear current question
            session.current_question = None
            
            logger.info(f"Question ended in room {room_code}, {correct_answers}/{total_answers} correct")
            
        except Exception as e:
            logger.error(f"Error ending question: {e}")
    
    async def handle_close_room(self, room_code: str):
        """Handle room closure from host"""
        try:
            session = game_storage.get_session(room_code)
            if not session:
                return
            
            session.is_active = False
            
            # Notify all players
            await self.broadcast_to_players(
                room_code,
                RoomClosedMessage(reason="Host closed the room")
            )
            
            # Close all connections
            await self.close_all_player_connections(room_code)
            
            # Clean up
            if room_code in self.host_connections:
                del self.host_connections[room_code]
            if room_code in self.player_connections:
                del self.player_connections[room_code]
            
            game_storage.remove_session(room_code)
            logger.info(f"Room {room_code} closed by host")
            
        except Exception as e:
            logger.error(f"Error closing room: {e}")
    
    async def send_to_host(self, room_code: str, message: BaseMessage, retries: int = 2):
        """Send message to host with retry logic"""
        if room_code not in self.host_connections:
            return False
        
        websocket = self.host_connections[room_code]
        
        for attempt in range(retries + 1):
            try:
                await websocket.send_text(message.model_dump_json())
                self.metrics['messages_sent'] += 1
                return True
            except Exception as e:
                logger.warning(f"Error sending to host (attempt {attempt + 1}): {e}")
                if attempt == retries:
                    logger.error(f"Failed to send to host after {retries + 1} attempts")
                    await self.disconnect_host(room_code)
                    self.metrics['errors'] += 1
                    return False
                await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
        
        return False
    
    async def broadcast_to_players(self, room_code: str, message: BaseMessage, exclude_player: str = None, retries: int = 1):
        """Broadcast message to all players in room with error handling"""
        if room_code not in self.player_connections:
            return 0
        
        message_json = message.model_dump_json()
        successful_sends = 0
        failed_players = []
        
        # Send to all players concurrently
        tasks = []
        for player_id, websocket in self.player_connections[room_code].items():
            if exclude_player and player_id == exclude_player:
                continue
            
            task = asyncio.create_task(
                self._send_to_player_with_retry(websocket, message_json, player_id, retries)
            )
            tasks.append((player_id, task))
        
        # Wait for all sends to complete
        for player_id, task in tasks:
            try:
                success = await task
                if success:
                    successful_sends += 1
                else:
                    failed_players.append(player_id)
            except Exception as e:
                logger.error(f"Task failed for player {player_id}: {e}")
                failed_players.append(player_id)
        
        # Clean up failed connections
        for player_id in failed_players:
            await self.disconnect_player(room_code, player_id)
        
        self.metrics['messages_sent'] += successful_sends
        return successful_sends
    
    async def _send_to_player_with_retry(self, websocket: WebSocket, message_json: str, player_id: str, retries: int):
        """Send message to single player with retry logic"""
        for attempt in range(retries + 1):
            try:
                await websocket.send_text(message_json)
                return True
            except Exception as e:
                if attempt == retries:
                    logger.error(f"Failed to send to player {player_id} after {retries + 1} attempts: {e}")
                    return False
                await asyncio.sleep(0.05 * (attempt + 1))
        return False
    
    async def send_error(self, websocket: WebSocket, error_message: str):
        """Send error message to websocket"""
        try:
            # Check if connection is still open
            if websocket.client_state.value == 3:  # 3 = CLOSED
                return
                
            error_msg = ErrorMessage(message=error_message)
            await websocket.send_text(error_msg.model_dump_json())
        except Exception as e:
            # Ignore errors for closed connections
            if "close message has been sent" not in str(e):
                logger.error(f"Error sending error message: {e}")
    
    async def close_all_player_connections(self, room_code: str):
        """Close all player connections in a room"""
        if room_code in self.player_connections:
            for player_id, websocket in list(self.player_connections[room_code].items()):
                try:
                    # Check if connection is still open before closing
                    if not websocket.client_state.value == 3:  # 3 = CLOSED
                        await websocket.close(code=1000, reason="Room closed")
                except Exception as e:
                    # Ignore close errors for already closed connections
                    if "close message has been sent" not in str(e):
                        logger.error(f"Error closing player connection {player_id}: {e}")

# Global connection manager instance
connection_manager = ConnectionManager()
