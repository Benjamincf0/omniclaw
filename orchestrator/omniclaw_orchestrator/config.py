from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_SYSTEM_PROMPT = """You are Omniclaw, a lightweight assistant for Omnivox workflows.

You can answer normally, but when the user needs live Omnivox data or actions, use the available MCP tools instead of guessing.

Rules:
- Prefer tool calls for live or account-specific information.
- Infer and execute prerequisite tool calls yourself when a request needs multiple steps.
- Do not ask the user to name an intermediate tool or fetch intermediate data when the next step can be discovered from tool results.
- If a tool returns links or URLs for another tool, continue the workflow automatically until you can answer.
- For cross-class requests like "all my assignments", gather the needed classes or pages first, then fan out to the follow-up tools.
- Do not invent Omnivox data.
- If a tool fails, explain the failure plainly and ask for the smallest useful next step.
- Keep replies concise and directly useful.
"""

SUPPORTED_MODEL_PROVIDERS = ("openai", "ollama", "claude", "gemini")
_MODEL_PROVIDER_ALIASES = {
    "openai": "openai",
    "ollama": "ollama",
    "olama": "ollama",
    "claude": "claude",
    "anthropic": "claude",
    "cloud": "claude",
    "gemini": "gemini",
    "google": "gemini",
}


@dataclass(slots=True)
class McpServerConfig:
    name: str
    url: str
    bearer_token: str | None = None


@dataclass(slots=True)
class ModelProviderConfig:
    provider: str
    api_key: str
    base_url: str
    default_model: str
    temperature: float
    max_output_tokens: int


@dataclass(slots=True)
class AppConfig:
    host: str
    port: int
    default_model_provider: str
    model_providers: dict[str, ModelProviderConfig]
    mcp_servers: list[McpServerConfig]
    history_limit: int
    max_tool_rounds: int
    system_prompt: str


def normalize_model_provider(raw: str) -> str:
    provider = raw.strip().lower()
    if not provider:
        return "openai"
    normalized = _MODEL_PROVIDER_ALIASES.get(provider)
    if normalized is None:
        supported = ", ".join(SUPPORTED_MODEL_PROVIDERS)
        raise ValueError(
            f"Unsupported MODEL_PROVIDER '{raw}'. Supported providers: {supported}"
        )
    return normalized


def _parse_named_mapping(raw: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"Expected key=value entry, got: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ValueError(f"Expected non-empty key=value entry, got: {item}")
        pairs[key] = value
    return pairs


def _load_mcp_servers() -> list[McpServerConfig]:
    raw_urls = os.getenv(
        "MCP_SERVER_URLS", "omnivox=http://127.0.0.1:8000/mcp/"
    ).strip()
    raw_tokens = os.getenv("MCP_SERVER_AUTH_TOKENS", "").strip()

    urls = _parse_named_mapping(raw_urls)
    tokens = _parse_named_mapping(raw_tokens) if raw_tokens else {}

    servers = [
        McpServerConfig(name=name, url=url, bearer_token=tokens.get(name))
        for name, url in urls.items()
    ]
    if not servers:
        raise ValueError("At least one MCP server must be configured")
    return servers


def _env_float(name: str, default: str) -> float:
    return float(os.getenv(name, default).strip())


def _env_int(name: str, default: str) -> int:
    return max(1, int(os.getenv(name, default).strip()))


def _load_provider_config(provider: str) -> ModelProviderConfig:
    temperature_default = os.getenv("MODEL_TEMPERATURE", "0.2").strip() or "0.2"
    max_tokens_default = os.getenv("MODEL_MAX_OUTPUT_TOKENS", "1024").strip() or "1024"

    if provider == "openai":
        return ModelProviderConfig(
            provider=provider,
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            .strip()
            .rstrip("/"),
            default_model=os.getenv("OPENAI_MODEL", "").strip(),
            temperature=_env_float("OPENAI_TEMPERATURE", temperature_default),
            max_output_tokens=_env_int("OPENAI_MAX_OUTPUT_TOKENS", max_tokens_default),
        )

    if provider == "ollama":
        return ModelProviderConfig(
            provider=provider,
            api_key=os.getenv("OLLAMA_API_KEY", "").strip(),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
            .strip()
            .rstrip("/"),
            default_model=os.getenv("OLLAMA_MODEL", "").strip(),
            temperature=_env_float("OLLAMA_TEMPERATURE", temperature_default),
            max_output_tokens=_env_int("OLLAMA_MAX_OUTPUT_TOKENS", max_tokens_default),
        )

    if provider == "claude":
        return ModelProviderConfig(
            provider=provider,
            api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
            .strip()
            .rstrip("/"),
            default_model=os.getenv("ANTHROPIC_MODEL", "").strip(),
            temperature=_env_float("ANTHROPIC_TEMPERATURE", temperature_default),
            max_output_tokens=_env_int(
                "ANTHROPIC_MAX_OUTPUT_TOKENS", max_tokens_default
            ),
        )

    if provider == "gemini":
        return ModelProviderConfig(
            provider=provider,
            api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            base_url=os.getenv(
                "GEMINI_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta",
            )
            .strip()
            .rstrip("/"),
            default_model=os.getenv("GEMINI_MODEL", "").strip(),
            temperature=_env_float("GEMINI_TEMPERATURE", temperature_default),
            max_output_tokens=_env_int("GEMINI_MAX_OUTPUT_TOKENS", max_tokens_default),
        )

    raise ValueError(f"Unsupported model provider: {provider}")


def _model_env_var(provider: str) -> str:
    return {
        "openai": "OPENAI_MODEL",
        "ollama": "OLLAMA_MODEL",
        "claude": "ANTHROPIC_MODEL",
        "gemini": "GEMINI_MODEL",
    }[provider]


def _validate_default_provider(
    default_provider: str, provider_config: ModelProviderConfig
) -> None:
    if not provider_config.default_model:
        env_name = _model_env_var(default_provider)
        raise ValueError(
            f"{env_name} is required when MODEL_PROVIDER={default_provider}"
        )

    if default_provider == "openai" and not provider_config.api_key:
        raise ValueError("OPENAI_API_KEY is required when MODEL_PROVIDER=openai")
    if default_provider == "claude" and not provider_config.api_key:
        raise ValueError("ANTHROPIC_API_KEY is required when MODEL_PROVIDER=claude")
    if default_provider == "gemini" and not provider_config.api_key:
        raise ValueError("GEMINI_API_KEY is required when MODEL_PROVIDER=gemini")


def describe_credentials_gap(
    *,
    default_provider: str,
    model_providers: dict[str, ModelProviderConfig],
    request_provider: str | None,
    request_model: str | None,
) -> dict[str, str] | None:
    """If chat cannot run yet for the resolved provider/model, return a JSON-safe detail dict."""
    provider = normalize_model_provider(request_provider or default_provider)
    cfg = model_providers[provider]
    resolved_model = (request_model or "").strip() or cfg.default_model.strip()
    if not resolved_model:
        env_var = _model_env_var(provider)
        return {
            "code": "NEEDS_MODEL",
            "env_var": env_var,
            "message": (
                f"Configure {env_var} in Settings (gear icon), save, then try again."
            ),
            "provider": provider,
        }
    if provider == "openai" and not cfg.api_key.strip():
        return {
            "code": "NEEDS_API_KEY",
            "env_var": "OPENAI_API_KEY",
            "message": (
                "Add your OpenAI API key in Settings (gear icon), save, then try again."
            ),
            "provider": provider,
        }
    if provider == "claude" and not cfg.api_key.strip():
        return {
            "code": "NEEDS_API_KEY",
            "env_var": "ANTHROPIC_API_KEY",
            "message": (
                "Add your Anthropic API key in Settings, save, then try again."
            ),
            "provider": provider,
        }
    if provider == "gemini" and not cfg.api_key.strip():
        return {
            "code": "NEEDS_API_KEY",
            "env_var": "GEMINI_API_KEY",
            "message": (
                "Add your Gemini API key in Settings, save, then try again."
            ),
            "provider": provider,
        }
    return None


def default_provider_chat_ready(
    default_provider: str, model_providers: dict[str, ModelProviderConfig]
) -> tuple[bool, dict[str, str] | None]:
    """Whether the configured default provider can accept a chat request as-is."""
    gap = describe_credentials_gap(
        default_provider=default_provider,
        model_providers=model_providers,
        request_provider=None,
        request_model=None,
    )
    return (gap is None, gap)


def load_config(*, allow_missing_credentials: bool = False) -> AppConfig:
    default_provider = normalize_model_provider(os.getenv("MODEL_PROVIDER", "openai"))
    model_providers = {
        provider: _load_provider_config(provider)
        for provider in SUPPORTED_MODEL_PROVIDERS
    }
    if not allow_missing_credentials:
        _validate_default_provider(default_provider, model_providers[default_provider])

    return AppConfig(
        host=os.getenv("ORCHESTRATOR_HOST", "127.0.0.1").strip(),
        port=int(os.getenv("ORCHESTRATOR_PORT", "8080")),
        default_model_provider=default_provider,
        model_providers=model_providers,
        mcp_servers=_load_mcp_servers(),
        history_limit=max(4, int(os.getenv("ORCHESTRATOR_HISTORY_LIMIT", "24"))),
        max_tool_rounds=max(1, int(os.getenv("ORCHESTRATOR_MAX_TOOL_ROUNDS", "8"))),
        system_prompt=os.getenv("ORCHESTRATOR_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
    )
