import os

# Must be set before any app module is imported (Settings() runs at module level)
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("JINA_API_KEY", "test-key")
