from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Set


@dataclass(frozen=True)
class AccessConfig:
    allowed_user_ids: frozenset[int]
    allowed_chat_ids: frozenset[int]

    @property
    def enabled(self) -> bool:
        return bool(self.allowed_user_ids or self.allowed_chat_ids)


def parse_id_list(raw_value: Optional[str]) -> frozenset[int]:
    if raw_value is None:
        return frozenset()

    parsed: Set[int] = set()
    for chunk in str(raw_value).replace("\n", ",").split(","):
        token = chunk.strip()
        if not token:
            continue
        parsed.add(int(token))
    return frozenset(parsed)


def build_access_config(
    allowed_user_ids: Optional[Iterable[int]] = None,
    allowed_chat_ids: Optional[Iterable[int]] = None,
) -> AccessConfig:
    return AccessConfig(
        allowed_user_ids=frozenset(allowed_user_ids or ()),
        allowed_chat_ids=frozenset(allowed_chat_ids or ()),
    )


def merge_access_configs(*configs: AccessConfig) -> AccessConfig:
    allowed_user_ids: Set[int] = set()
    allowed_chat_ids: Set[int] = set()
    for config in configs:
        allowed_user_ids.update(config.allowed_user_ids)
        allowed_chat_ids.update(config.allowed_chat_ids)
    return build_access_config(
        allowed_user_ids=sorted(allowed_user_ids),
        allowed_chat_ids=sorted(allowed_chat_ids),
    )


def is_authorized_chat(
    chat_id: Optional[int],
    user_id: Optional[int],
    config: AccessConfig,
) -> bool:
    if not config.enabled:
        return True
    if config.allowed_chat_ids and chat_id not in config.allowed_chat_ids:
        return False
    if config.allowed_user_ids and user_id not in config.allowed_user_ids:
        return False
    return True


def requires_explicit_access(
    access_config: AccessConfig,
    admin_config: Optional[AccessConfig] = None,
) -> bool:
    return access_config.enabled or bool(admin_config and admin_config.enabled)


def is_authorized_for_bot(
    chat_id: Optional[int],
    user_id: Optional[int],
    access_config: AccessConfig,
    admin_config: Optional[AccessConfig] = None,
) -> bool:
    if admin_config and is_authorized_chat(chat_id, user_id, admin_config):
        return True
    if not requires_explicit_access(access_config, admin_config):
        return True
    if not access_config.enabled:
        return False
    return is_authorized_chat(chat_id, user_id, access_config)


def format_identity_message(
    user_id: Optional[int],
    chat_id: Optional[int],
    username: Optional[str],
    chat_type: Optional[str],
    authorized: bool,
) -> str:
    username_text = "@{0}".format(username) if username else "не указан"
    access_text = "разрешён" if authorized else "запрещён"
    return (
        "Ваши данные для настройки доступа:\n"
        "user_id: {0}\n"
        "chat_id: {1}\n"
        "username: {2}\n"
        "chat_type: {3}\n"
        "текущий доступ: {4}"
    ).format(
        user_id if user_id is not None else "unknown",
        chat_id if chat_id is not None else "unknown",
        username_text,
        chat_type or "unknown",
        access_text,
    )


def load_access_store(path: Path) -> AccessConfig:
    if not path.exists():
        return build_access_config()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return build_access_config()

    return build_access_config(
        allowed_user_ids=raw.get("allowed_user_ids") or [],
        allowed_chat_ids=raw.get("allowed_chat_ids") or [],
    )


def save_access_store(config: AccessConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "allowed_user_ids": sorted(config.allowed_user_ids),
        "allowed_chat_ids": sorted(config.allowed_chat_ids),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def add_allowed_user(config: AccessConfig, user_id: int) -> AccessConfig:
    return build_access_config(
        allowed_user_ids=set(config.allowed_user_ids) | {int(user_id)},
        allowed_chat_ids=config.allowed_chat_ids,
    )


def remove_allowed_user(config: AccessConfig, user_id: int) -> AccessConfig:
    return build_access_config(
        allowed_user_ids={value for value in config.allowed_user_ids if value != int(user_id)},
        allowed_chat_ids=config.allowed_chat_ids,
    )


def add_allowed_chat(config: AccessConfig, chat_id: int) -> AccessConfig:
    return build_access_config(
        allowed_user_ids=config.allowed_user_ids,
        allowed_chat_ids=set(config.allowed_chat_ids) | {int(chat_id)},
    )


def remove_allowed_chat(config: AccessConfig, chat_id: int) -> AccessConfig:
    return build_access_config(
        allowed_user_ids=config.allowed_user_ids,
        allowed_chat_ids={value for value in config.allowed_chat_ids if value != int(chat_id)},
    )


def format_access_list(config: AccessConfig) -> str:
    user_list = ", ".join(str(value) for value in sorted(config.allowed_user_ids)) or "пусто"
    chat_list = ", ".join(str(value) for value in sorted(config.allowed_chat_ids)) or "пусто"
    return "Текущий доступ:\nallowed_user_ids: {0}\nallowed_chat_ids: {1}".format(
        user_list,
        chat_list,
    )


__all__ = [
    "AccessConfig",
    "add_allowed_chat",
    "add_allowed_user",
    "build_access_config",
    "format_access_list",
    "format_identity_message",
    "is_authorized_chat",
    "is_authorized_for_bot",
    "load_access_store",
    "merge_access_configs",
    "parse_id_list",
    "requires_explicit_access",
    "remove_allowed_chat",
    "remove_allowed_user",
    "save_access_store",
]
