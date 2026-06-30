"""
Logger utility for HyperAgent simulation.

Provides centralized logging configuration for all agents and components.

Based on the HyperAgent architecture from FSoft-AI4Code:
https://github.com/FSoft-AI4Code/HyperAgent
"""

import logging
import sys
from typing import Optional
from datetime import datetime


def setup_logger(log_file: Optional[str] = None, verbose: bool = True) -> logging.Logger:
    """
    Setup and return a configured logger for HyperAgent simulation.
    
    Args:
        log_file: Optional file to log to
        verbose: Whether to log to console
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("hyperagent")
    logger.setLevel(logging.INFO if verbose else logging.WARNING)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler
    if verbose:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO if verbose else logging.WARNING)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def log_agent_action(logger: logging.Logger, agent_name: str, action: str, details: Optional[dict] = None):
    """
    Log an agent action.
    
    Args:
        logger: Logger instance
        agent_name: Name of the agent
        action: Action performed
        details: Optional details about the action
    """
    message = f"[{agent_name}] {action}"
    if details:
        message += f" - {details}"
    logger.info(message)


def log_message_event(logger: logging.Logger, event_type: str, sender: str, receiver: str, content: Optional[dict] = None):
    """
    Log a message event between agents.
    
    Args:
        logger: Logger instance
        event_type: Type of message event (sent, received, etc.)
        sender: Name of the sending agent
        receiver: Name of the receiving agent
        content: Optional message content
    """
    message = f"[MSG] {event_type}: {sender} -> {receiver}"
    if content:
        message += f" | {str(content)[:100]}"
    logger.debug(message)


class HyperAgentLogger:
    """
    Centralized logger for HyperAgent simulation (legacy compatibility).
    """
    
    _loggers = {}
    
    @classmethod
    def get_logger(cls, name: str, level: int = logging.INFO, 
                   log_file: Optional[str] = None, 
                   verbose: bool = True) -> logging.Logger:
        """
        Get or create a logger with the specified configuration.
        
        Args:
            name: Logger name
            level: Logging level
            log_file: Optional file to log to
            verbose: Whether to log to console
            
        Returns:
            Configured logger instance
        """
        if name in cls._loggers:
            return cls._loggers[name]
        
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Console handler
        if verbose:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
        
        # File handler
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(level)
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        
        cls._loggers[name] = logger
        return logger
