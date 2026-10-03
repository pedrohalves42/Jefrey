"""System Plugin for Jefrey
Provides system control and monitoring capabilities.
"""

__version__ = "1.0.0"

# Plugin metadata
PLUGIN_NAME = "system"
PLUGIN_DESCRIPTION = "System control and monitoring"
PLUGIN_VERSION = "1.0.0"
PLUGIN_AUTHOR = "Jefrey Team"

# Plugin configuration
PLUGIN_CONFIG = {
    "supported_commands": ["get_system_info", "restart", "shutdown", "status"],
    "required_params": [],
    "optional_params": ["detail_level"],
}

# Plugin state
_plugin_state = {
    "enabled": True,
    "initialized": False,
}

def init_plugin():
    """Initialize the system plugin."""
    global _plugin_state
    _plugin_state["initialized"] = True
    return {"status": "initialized", "plugin": PLUGIN_NAME}

def get_system_info():
    """Get system information."""
    return {"status": "info retrieved", "plugin": PLUGIN_NAME, "data": {"os": "Windows", "python": "3.10+"}}

def restart():
    """Restart the system."""
    return {"status": "restart initiated", "plugin": PLUGIN_NAME}

def shutdown():
    """Shutdown the system."""
    return {"status": "shutdown initiated", "plugin": PLUGIN_NAME}

def status():
    """Get system status."""
    return {"status": "operational", "plugin": PLUGIN_NAME}