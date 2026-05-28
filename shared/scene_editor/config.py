"""Configuration defaults for the local scene editor."""

# Gemma is the recommended default for atmospheric screenplay rewriting.
# Qwen models remain configurable in the UI, but may introduce residual reasoning.
DEFAULT_MODEL = "gemma4:latest"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_NUM_CTX = 8192
DEFAULT_NUM_PREDICT = 16000
DEFAULT_MAX_TOKENS = DEFAULT_NUM_PREDICT
DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_TIMEOUT_SECONDS = 600
