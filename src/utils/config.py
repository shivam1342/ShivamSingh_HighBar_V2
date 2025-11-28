"""
Configuration loader utility
"""
import yaml
from pathlib import Path
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """
    Load YAML configuration file
    
    Args:
        config_path: Path to config.yaml
        
    Returns:
        Configuration dictionary
    """
    try:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
        
        logger.info(f"Configuration loaded from {config_path}")
        return config
        
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        raise


def setup_logging(config: Dict[str, Any]):
    """
    Setup logging based on configuration
    
    Args:
        config: Configuration dictionary
    """
    log_config = config.get("logging", {})
    level = log_config.get("level", "INFO")
    log_format = log_config.get("format", "text")
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info(f"Logging configured: level={level}, format={log_format}")
