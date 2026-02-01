"""
Configuration management for LLM Awareness Emergence System
"""

from .default_config import DEFAULT_CONFIG, load_config, save_config, get_config_path

__all__ = ["DEFAULT_CONFIG", "load_config", "save_config", "get_config_path"]
