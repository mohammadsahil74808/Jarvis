# actions/file_controller.py
"""
File Controller Wrapper
This module acts as a formal interface for the agent system to interact with file_manager.py.
It ensures compatibility with the AgentExecutor while providing clean, reusable wrappers.
"""

from actions.file_manager import file_manager

def file_controller(parameters: dict, player=None) -> str:
    """
    Consolidated entry point for the agent executor.
    Delegates all actions to the core file_manager logic.
    """
    return file_manager(parameters, player=player)

def list_files(parameters: dict, player=None) -> str:
    """Wrapper for listing files."""
    parameters["action"] = "list"
    return file_manager(parameters, player=player)

def read_file(parameters: dict, player=None) -> str:
    """Wrapper for reading documents (txt, pdf, docx)."""
    parameters["action"] = "read"
    return file_manager(parameters, player=player)

def write_file(parameters: dict, player=None) -> str:
    """Wrapper for writing or appending content to files."""
    parameters["action"] = "write"
    return file_manager(parameters, player=player)

def create_file(parameters: dict, player=None) -> str:
    """Wrapper for creating new files."""
    parameters["action"] = "create_file"
    return file_manager(parameters, player=player)

def delete_file(parameters: dict, player=None) -> str:
    """Wrapper for deleting files or folders."""
    parameters["action"] = "delete"
    return file_manager(parameters, player=player)

def move_file(parameters: dict, player=None) -> str:
    """Wrapper for moving files or folders."""
    parameters["action"] = "move"
    return file_manager(parameters, player=player)

def copy_file(parameters: dict, player=None) -> str:
    """Wrapper for copying files or folders."""
    parameters["action"] = "copy"
    return file_manager(parameters, player=player)

def find_files(parameters: dict, player=None) -> str:
    """Wrapper for searching files by name or extension."""
    parameters["action"] = "find"
    return file_manager(parameters, player=player)

def get_largest(parameters: dict, player=None) -> str:
    """Wrapper for finding the largest files in a path."""
    parameters["action"] = "largest"
    return file_manager(parameters, player=player)

def get_disk_usage(parameters: dict, player=None) -> str:
    """Wrapper for checking disk space usage."""
    parameters["action"] = "disk_usage"
    return file_manager(parameters, player=player)
