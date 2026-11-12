"""Resolve runtime configuration from CLI arguments and the environment."""

from __future__ import annotations

import argparse
import getpass
import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    """Raised when the provided configuration is invalid."""


@dataclass
class Config:
    base_url: str
    token: str
    output: Path
    timeout: float
    retries: int
    include_discussions: bool
    dry_run: bool

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> Config:
        if args.timeout <= 0:
            raise ConfigError("timeout must be positive")
        if args.retries < 0:
            raise ConfigError("retries cannot be negative")

        token = os.getenv("CANVAS_API_TOKEN") or getpass.getpass("Canvas API token: ").strip()
        if not token:
            raise ConfigError("Canvas API token is required")

        return cls(
            base_url=args.base_url,
            token=token,
            output=args.output,
            timeout=args.timeout,
            retries=args.retries,
            include_discussions=args.include_discussions,
            dry_run=args.dry_run,
        )
