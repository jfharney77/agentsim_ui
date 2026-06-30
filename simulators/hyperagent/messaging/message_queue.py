"""
Message queue for inter-agent communication in HyperAgent.

Facilitates communication between the four specialized agents:
- Planner, Navigator, Editor, Executor

Based on the HyperAgent architecture from FSoft-AI4Code:
https://github.com/FSoft-AI4Code/HyperAgent
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import threading
import queue


@dataclass
class Message:
    """
    Represents a message between agents.
    """
    sender: str
    receiver: str
    content: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    message_type: str = "general"  # general, feedback, request, response
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "message_type": self.message_type
        }


class MessageQueue:
    """
    Thread-safe message queue for agent communication.
    
    Enables centralized communication and coordination between agents.
    """
    
    def __init__(self):
        """Initialize the message queue."""
        self._queue = queue.Queue()
        self._history: List[Message] = []
        self._lock = threading.Lock()
        
    def send(self, sender: str, receiver: str, content: Dict[str, Any], message_type: str = "general") -> None:
        """
        Send a message from one agent to another.
        
        Args:
            sender: Name of the sending agent
            receiver: Name of the receiving agent
            content: Message content
            message_type: Type of message (general, feedback, request, response)
        """
        message = Message(sender=sender, receiver=receiver, content=content, message_type=message_type)
        
        with self._lock:
            self._queue.put(message)
            self._history.append(message)
    
    def receive(self, agent_name: str, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Receive a message for a specific agent.
        
        Args:
            agent_name: Name of the agent receiving the message
            timeout: Optional timeout in seconds
            
        Returns:
            Message dictionary if available, None otherwise
        """
        # Check if there's a message for this agent in the queue
        try:
            if timeout:
                message = self._queue.get(timeout=timeout)
            else:
                message = self._queue.get(block=False)
            
            if message.receiver == agent_name or message.receiver == "broadcast":
                return message.to_dict()
            else:
                # Put it back if it's not for this agent
                self._queue.put(message)
                return None
        except queue.Empty:
            return None
    
    def get_history(self, agent_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get message history.
        
        Args:
            agent_name: Optional filter for specific agent
            
        Returns:
            List of message dictionaries
        """
        with self._lock:
            if agent_name:
                filtered = [msg for msg in self._history 
                           if msg.sender == agent_name or msg.receiver == agent_name]
                return [msg.to_dict() for msg in filtered]
            return [msg.to_dict() for msg in self._history]
    
    def clear_history(self) -> None:
        """Clear message history."""
        with self._lock:
            self._history.clear()
    
    def get_pending_count(self, agent_name: Optional[str] = None) -> int:
        """
        Get count of pending messages.
        
        Args:
            agent_name: Optional filter for specific agent
            
        Returns:
            Number of pending messages
        """
        if agent_name:
            # Count messages for specific agent
            count = 0
            temp_messages = []
            while not self._queue.empty():
                msg = self._queue.get()
                if msg.receiver == agent_name or msg.receiver == "broadcast":
                    count += 1
                temp_messages.append(msg)
            
            # Put messages back
            for msg in temp_messages:
                self._queue.put(msg)
            
            return count
        else:
            return self._queue.qsize()
    
    def get_log(self) -> List[Dict[str, Any]]:
        """
        Get the complete message log.
        
        Returns:
            List of all message dictionaries
        """
        with self._lock:
            return [msg.to_dict() for msg in self._history]
    
    def clear(self):
        """Clear the message queue and history."""
        with self._lock:
            while not self._queue.empty():
                self._queue.get()
            self._history.clear()
