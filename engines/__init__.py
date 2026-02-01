"""
Core engines for LLM Awareness Emergence System
"""

from .memory_system import MemorySystem
from .dreaming_engine import DreamingEngine
from .thinking_habits import ThinkingHabitsEngine, RealtimeThinkingHabits
from .self_reflection import SelfReflectionEngine, RealtimeObserver
from .awareness_engine import AwarenessEngine, AITextDetector, AWARENESS_CATEGORIES, ENHANCED_AWARENESS_TRIGGERS
from .awareness_database import AwarenessDatabase
from .session_manager import Session, SessionManager
from .lora_trainer import LoRATrainer, TrainingNotifier
from .personality_axis import PersonalityAxisEngine, PERSONALITY_AXES

__all__ = [
    # Memory & Dreaming
    "MemorySystem",
    "DreamingEngine",
    # Thinking Habits
    "ThinkingHabitsEngine",
    "RealtimeThinkingHabits",
    # Self Reflection
    "SelfReflectionEngine",
    "RealtimeObserver",
    # Awareness
    "AwarenessEngine",
    "AITextDetector",
    "AwarenessDatabase",
    "AWARENESS_CATEGORIES",
    "ENHANCED_AWARENESS_TRIGGERS",
    # Personality Axis
    "PersonalityAxisEngine",
    "PERSONALITY_AXES",
    # Session
    "Session",
    "SessionManager",
    # Training
    "LoRATrainer",
    "TrainingNotifier",
]
