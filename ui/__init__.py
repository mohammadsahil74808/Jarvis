from .jarvis_ui import JarvisUI

# Export widgets for convenience (optional, but good for cleanliness)
try:
    from .web_search_widget    import WebSearchWidget
    from .deep_research_widget import DeepResearchWidget
    from .file_search_widget   import FileSearchWidget
    from .floating_widget      import FloatingWidget
except ImportError:
    pass
