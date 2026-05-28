"""Small requests-based client for local Ollama generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from .config import DEFAULT_NUM_CTX, DEFAULT_OLLAMA_URL, DEFAULT_TIMEOUT_SECONDS


class OllamaError(RuntimeError):
    """Raised when Ollama cannot complete a generation."""


def model_supports_no_think_switch(model: str) -> bool:
    """Return true for Qwen-family models that commonly accept /no_think."""

    return "qwen" in model.lower()


def prompt_for_model(model: str, prompt: str) -> str:
    """Apply model-specific prompt switches without changing scene instructions."""

    if model_supports_no_think_switch(model):
        return f"/no_think\n\n{prompt}"
    return prompt


@dataclass(frozen=True)
class OllamaClient:
    """Minimal wrapper around Ollama's /api/generate endpoint."""

    url: str = DEFAULT_OLLAMA_URL
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate text with a local Ollama model."""

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt_for_model(model, prompt),
            "stream": False,
            "think": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": DEFAULT_NUM_CTX,
            },
        }
        try:
            response = requests.post(self.url, json=payload, timeout=self.timeout_seconds)
        except requests.exceptions.ConnectionError as exc:
            raise OllamaError(
                "Ollama no parece estar levantado en http://localhost:11434."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise OllamaError("Timeout esperando respuesta de Ollama.") from exc
        except requests.exceptions.RequestException as exc:
            raise OllamaError(f"Error llamando a Ollama: {exc}") from exc

        if response.status_code == 404:
            raise OllamaError(
                f"Modelo no encontrado o endpoint no disponible: {model}. "
                f"Prueba con `ollama pull {model}`."
            )
        if response.status_code >= 400:
            raise OllamaError(f"Ollama devolvio HTTP {response.status_code}: {response.text}")

        data = response.json()
        if "error" in data:
            raise OllamaError(str(data["error"]))
        generated = data.get("response")
        if not isinstance(generated, str):
            raise OllamaError("Respuesta de Ollama sin campo `response` valido.")
        cleaned = generated.strip()
        if not cleaned:
            raise OllamaError(
                "Ollama devolvio una respuesta vacia. Prueba a subir `Max tokens`, "
                "usar un modelo no-razonador, o cambiar de modelo en la UI."
            )
        return cleaned
