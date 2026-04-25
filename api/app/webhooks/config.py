"""Webhook configuration loader."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Fixed configuration path
CONFIG_PATH = Path("config/webhooks.yaml")
DOCKER_SECRETS_PATH = Path("/run/secrets")


@dataclass
class WebhookEndpoint:
    """Webhook endpoint configuration."""

    id: str
    url: str
    secret: str
    events: list[str]
    enabled: bool = True
    description: str = ""

    def subscribes_to(self, event_type: str) -> bool:
        """Check if this endpoint subscribes to the given event type."""
        return event_type in self.events


@dataclass
class WebhookSettings:
    """Global webhook settings."""

    max_retries: int = 5
    retry_base_delay_seconds: int = 2
    retry_max_delay_seconds: int = 60
    retry_jitter_ratio: float = 0.0
    delivery_timeout_seconds: int = 30
    log_retention_days: int = 30


@dataclass
class WebhookConfig:
    """Complete webhook configuration."""

    endpoints: list[WebhookEndpoint] = field(default_factory=list)
    settings: WebhookSettings = field(default_factory=WebhookSettings)


class WebhookConfigLoader:
    """Loads and manages webhook endpoint configurations."""

    _config: WebhookConfig | None = None
    _env_var_secrets: set[str] = set()  # Track secrets loaded from env vars

    @classmethod
    def load(cls) -> WebhookConfig:
        """Load endpoints from config/webhooks.yaml."""
        cls._env_var_secrets.clear()

        if not CONFIG_PATH.exists():
            logger.info(
                "Webhook configuration not found at %s. Webhooks disabled.",
                CONFIG_PATH,
            )
            cls._config = WebhookConfig()
            return cls._config

        try:
            with open(CONFIG_PATH) as f:
                raw_config = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            logger.error("Failed to parse webhook configuration: %s", e)
            cls._config = WebhookConfig()
            return cls._config

        raw_endpoints = raw_config.get("endpoints", [])
        cls._validate_unique_endpoint_ids(raw_endpoints)

        endpoints = []
        for ep_data in raw_endpoints:
            try:
                endpoint = cls._parse_endpoint(ep_data)
                if endpoint:
                    endpoints.append(endpoint)
            except ValueError as e:
                logger.warning("Skipping invalid endpoint: %s", e)

        settings_data = raw_config.get("settings", {})
        cls._validate_settings(settings_data)
        settings = WebhookSettings(
            max_retries=settings_data.get("max_retries", 5),
            retry_base_delay_seconds=settings_data.get("retry_base_delay_seconds", 2),
            retry_max_delay_seconds=settings_data.get("retry_max_delay_seconds", 60),
            retry_jitter_ratio=float(settings_data.get("retry_jitter_ratio", 0.0)),
            delivery_timeout_seconds=settings_data.get("delivery_timeout_seconds", 30),
            log_retention_days=settings_data.get("log_retention_days", 30),
        )

        cls._config = WebhookConfig(endpoints=endpoints, settings=settings)

        # Log warnings for env var secrets
        cls._log_secret_warnings()

        logger.info(
            "Loaded %d webhook endpoint(s) from %s",
            len(endpoints),
            CONFIG_PATH,
        )
        return cls._config

    @staticmethod
    def _validate_unique_endpoint_ids(endpoints: list[dict[str, Any]]) -> None:
        """Reject duplicate endpoint IDs to keep operational references unambiguous."""
        seen_ids: set[str] = set()
        for endpoint in endpoints:
            endpoint_id = endpoint.get("id")
            if not endpoint_id:
                continue
            if endpoint_id in seen_ids:
                raise ValueError(f"Duplicate webhook endpoint id detected: {endpoint_id}")
            seen_ids.add(endpoint_id)

    @classmethod
    def _validate_settings(cls, settings_data: dict[str, Any]) -> None:
        """Validate webhook settings before applying them."""
        cls._validate_non_negative_int_setting(settings_data, "retry_base_delay_seconds")
        cls._validate_non_negative_int_setting(settings_data, "retry_max_delay_seconds")

        retry_base_delay_seconds = settings_data.get("retry_base_delay_seconds", 2)
        retry_max_delay_seconds = settings_data.get("retry_max_delay_seconds", 60)
        if retry_max_delay_seconds < retry_base_delay_seconds:
            raise ValueError(
                "settings.retry_max_delay_seconds must be greater than or equal to "
                "settings.retry_base_delay_seconds"
            )
        retry_jitter_ratio = settings_data.get("retry_jitter_ratio", 0.0)
        if not isinstance(retry_jitter_ratio, int | float):
            raise ValueError("settings.retry_jitter_ratio must be a number")
        if retry_jitter_ratio < 0 or retry_jitter_ratio > 1:
            raise ValueError("settings.retry_jitter_ratio must be in range [0, 1]")

        retry_backoff_ms = settings_data.get("retry_backoff_ms")
        if retry_backoff_ms is None:
            return

        if isinstance(retry_backoff_ms, int):
            if retry_backoff_ms < 0:
                raise ValueError("settings.retry_backoff_ms must be a non-negative integer")
            return

        if not isinstance(retry_backoff_ms, list) or not retry_backoff_ms:
            raise ValueError("settings.retry_backoff_ms must be a non-empty array of integers")

        prev_value = -1
        for idx, value in enumerate(retry_backoff_ms):
            if not isinstance(value, int) or value < 0:
                raise ValueError(
                    f"settings.retry_backoff_ms[{idx}] must be a non-negative integer"
                )
            if idx > 0 and value < prev_value:
                raise ValueError(
                    f"settings.retry_backoff_ms[{idx}] must be greater than or equal to "
                    f"settings.retry_backoff_ms[{idx - 1}]"
                )
            prev_value = value

    @staticmethod
    def _validate_non_negative_int_setting(settings_data: dict[str, Any], key: str) -> None:
        value = settings_data.get(key)
        if value is None:
            return
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"settings.{key} must be a non-negative integer")

    @classmethod
    def reload(cls) -> WebhookConfig:
        """Reload configuration (for hot-reload)."""
        return cls.load()

    @classmethod
    def get_config(cls) -> WebhookConfig:
        """Get current configuration, loading if necessary."""
        if cls._config is None:
            cls.load()
        return cls._config  # type: ignore

    @classmethod
    def get_endpoints_for_event(cls, event_type: str) -> list[WebhookEndpoint]:
        """Get all enabled endpoints subscribed to an event type."""
        config = cls.get_config()
        return [ep for ep in config.endpoints if ep.enabled and ep.subscribes_to(event_type)]

    @classmethod
    def _parse_endpoint(cls, data: dict[str, Any]) -> WebhookEndpoint | None:
        """Parse and validate endpoint configuration."""
        endpoint_id = data.get("id")
        url = data.get("url")
        secret_ref = data.get("secret")
        events = data.get("events", [])
        enabled = data.get("enabled", True)
        description = data.get("description", "")

        # Validate required fields
        if not endpoint_id:
            raise ValueError("Endpoint missing 'id' field")
        if not url:
            raise ValueError(f"Endpoint '{endpoint_id}' missing 'url' field")
        if not secret_ref:
            raise ValueError(f"Endpoint '{endpoint_id}' missing 'secret' field")
        if not events:
            raise ValueError(f"Endpoint '{endpoint_id}' missing 'events' field")
        if not isinstance(events, list):
            raise ValueError(f"Endpoint '{endpoint_id}' events must be an array")

        normalized_events: list[str] = []
        seen_events: set[str] = set()
        for idx, event in enumerate(events):
            if not isinstance(event, str):
                raise ValueError(
                    f"Endpoint '{endpoint_id}' events[{idx}] must be a string"
                )
            normalized_event = event.strip()
            if not normalized_event:
                raise ValueError(
                    f"Endpoint '{endpoint_id}' events contains empty element at index {idx}"
                )
            if normalized_event in seen_events:
                raise ValueError(
                    f"Endpoint '{endpoint_id}' events contains duplicated element: {normalized_event}"
                )
            seen_events.add(normalized_event)
            normalized_events.append(normalized_event)

        # Validate HTTPS
        if not url.startswith("https://"):
            raise ValueError(f"Endpoint '{endpoint_id}' URL must use HTTPS: {url}")

        # Resolve secret
        secret, is_docker_secret = cls._resolve_secret(secret_ref, endpoint_id)
        if not secret:
            raise ValueError(f"Endpoint '{endpoint_id}' secret could not be resolved: {secret_ref}")

        if not is_docker_secret:
            cls._env_var_secrets.add(secret_ref)

        return WebhookEndpoint(
            id=endpoint_id,
            url=url,
            secret=secret,
            events=normalized_events,
            enabled=enabled,
            description=description,
        )

    @classmethod
    def _resolve_secret(cls, secret_ref: str, endpoint_id: str) -> tuple[str | None, bool]:
        """
        Resolve secret value from Docker Secrets or environment variable.
        Returns (secret_value, is_docker_secret).
        """
        # Check for ${VAR_NAME} pattern
        match = re.match(r"^\$\{(\w+)\}$", secret_ref)
        if not match:
            # Literal value (not recommended but allowed)
            logger.warning(
                "Endpoint '%s' uses literal secret value. "
                "Use ${VAR_NAME} or Docker Secrets instead.",
                endpoint_id,
            )
            return secret_ref, False

        var_name = match.group(1)

        # Try Docker Secrets first (preferred)
        secret_file = DOCKER_SECRETS_PATH / var_name.lower()
        if secret_file.exists():
            try:
                return secret_file.read_text().strip(), True
            except OSError as e:
                logger.warning(
                    "Failed to read Docker Secret %s: %s",
                    secret_file,
                    e,
                )

        # Fall back to environment variable
        env_value = os.environ.get(var_name)
        if env_value:
            return env_value, False

        return None, False

    @classmethod
    def _log_secret_warnings(cls) -> None:
        """Log warnings for secrets loaded from environment variables."""
        for secret_ref in cls._env_var_secrets:
            match = re.match(r"^\$\{(\w+)\}$", secret_ref)
            if match:
                var_name = match.group(1)
                logger.warning(
                    "Webhook secret '%s' loaded from environment variable. "
                    "For production, use Docker Secrets: /run/secrets/%s "
                    "See: https://docs.docker.com/engine/swarm/secrets/",
                    var_name,
                    var_name.lower(),
                )
