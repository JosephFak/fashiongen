"""Validated, server-only configuration. No secrets are exposed to the browser."""

import os
from dataclasses import dataclass, field


def boolean(name: str, default: bool) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    if value not in {"true", "false", "1", "0"}:
        raise ValueError(f"{name} must be true/false or 1/0.")
    return value in {"true", "1"}


def integer(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


@dataclass(frozen=True)
class Settings:
    generation_mode: str = "demo"
    generation_provider: str = "local"
    search_mode: str = "demo"
    public_deployment: bool = False
    host: str = "127.0.0.1"
    port: int = 8888
    model_id: str = "stabilityai/stable-diffusion-3.5-medium"
    model_device: str = "auto"
    quantize_4bit: bool = True
    cpu_offload: bool = True
    inference_steps: int = 40
    image_size: int = 1024
    imgbb_expiration: int = 600
    max_upload_bytes: int = 10 * 1024 * 1024
    generation_hour_limit: int = 10
    generation_day_limit: int = 20
    search_hour_limit: int = 20
    search_day_limit: int = 100
    hf_token: str = field(default="", repr=False)
    replicate_api_token: str = field(default="", repr=False)
    imgbb_api_key: str = field(default="", repr=False)
    serpapi_api_key: str = field(default="", repr=False)

    @classmethod
    def from_env(cls):
        config = cls(
            generation_mode=os.getenv("GENERATION_MODE", "demo").strip().lower(),
            generation_provider=os.getenv("GENERATION_PROVIDER", "local").strip().lower(),
            search_mode=os.getenv("SEARCH_MODE", "demo").strip().lower(),
            public_deployment=boolean("PUBLIC_DEPLOYMENT", False),
            host=os.getenv("HOST", "127.0.0.1"),
            port=integer("PORT", 8888, 1, 65535),
            model_device=os.getenv("MODEL_DEVICE", "auto").strip().lower(),
            quantize_4bit=boolean("QUANTIZE_4BIT", True),
            cpu_offload=boolean("CPU_OFFLOAD", True),
            inference_steps=integer("INFERENCE_STEPS", 40, 1, 100),
            image_size=integer("IMAGE_SIZE", 1024, 512, 1536),
            imgbb_expiration=integer("IMGBB_EXPIRATION", 600, 60, 15552000),
            generation_hour_limit=integer("GENERATION_HOUR_LIMIT", 10, 1, 10000),
            generation_day_limit=integer("GENERATION_DAY_LIMIT", 20, 1, 100000),
            search_hour_limit=integer("SEARCH_HOUR_LIMIT", 20, 1, 10000),
            search_day_limit=integer("SEARCH_DAY_LIMIT", 100, 1, 100000),
            hf_token=os.getenv("HF_TOKEN", "").strip(),
            replicate_api_token=os.getenv("REPLICATE_API_TOKEN", "").strip(),
            imgbb_api_key=os.getenv("IMGBB_API_KEY", "").strip(),
            serpapi_api_key=os.getenv("SERPAPI_API_KEY", "").strip(),
        )
        config.validate()
        return config

    def validate(self):
        if self.generation_mode not in {"demo", "live"} or self.search_mode not in {"demo", "live"}:
            raise ValueError("GENERATION_MODE and SEARCH_MODE must be demo or live.")
        if self.generation_provider not in {"local", "replicate"}:
            raise ValueError("GENERATION_PROVIDER must be local or replicate.")
        if self.public_deployment and (self.generation_mode != "live" or self.search_mode != "live"):
            raise ValueError("Public deployment requires live generation and live search; demo data is disabled.")
        if self.generation_mode == "live" and self.generation_provider == "replicate" and not self.replicate_api_token:
            raise ValueError("Hosted generation requires REPLICATE_API_TOKEN in the server environment.")
        if self.model_device not in {"auto", "cuda", "cpu", "mps"}:
            raise ValueError("MODEL_DEVICE must be auto, cuda, mps, or cpu.")
        if self.image_size % 64:
            raise ValueError("IMAGE_SIZE must be a multiple of 64.")
        if self.search_mode == "live" and not (self.imgbb_api_key and self.serpapi_api_key):
            raise ValueError("Live search requires IMGBB_API_KEY and SERPAPI_API_KEY in the server environment.")
