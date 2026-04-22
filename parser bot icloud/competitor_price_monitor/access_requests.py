from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class AccessRequest:
    request_id: str
    user_id: int
    chat_id: int
    username: Optional[str]
    full_name: str
    phone_number: str
    requested_at: str
    status: str = "pending"
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[int] = None


def load_access_requests(path: Path) -> Dict[str, AccessRequest]:
    if not path.exists():
        return {}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    result: Dict[str, AccessRequest] = {}
    for item in raw:
        request = AccessRequest(
            request_id=str(item.get("request_id") or ""),
            user_id=int(item.get("user_id")),
            chat_id=int(item.get("chat_id")),
            username=item.get("username"),
            full_name=str(item.get("full_name") or ""),
            phone_number=str(item.get("phone_number") or ""),
            requested_at=str(item.get("requested_at") or ""),
            status=str(item.get("status") or "pending"),
            reviewed_at=item.get("reviewed_at"),
            reviewed_by=item.get("reviewed_by"),
        )
        if request.request_id:
            result[request.request_id] = request
    return result


def save_access_requests(path: Path, requests: Dict[str, AccessRequest]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(request) for request in sorted(requests.values(), key=lambda item: item.requested_at)]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def create_or_refresh_access_request(
    path: Path,
    *,
    user_id: int,
    chat_id: int,
    username: Optional[str],
    full_name: str,
    phone_number: str,
    requested_at: str,
) -> AccessRequest:
    requests = load_access_requests(path)
    for request in requests.values():
        if request.user_id == int(user_id) and request.chat_id == int(chat_id) and request.status == "pending":
            updated = AccessRequest(
                request_id=request.request_id,
                user_id=request.user_id,
                chat_id=request.chat_id,
                username=username,
                full_name=full_name,
                phone_number=phone_number,
                requested_at=requested_at,
                status="pending",
                reviewed_at=None,
                reviewed_by=None,
            )
            requests[updated.request_id] = updated
            save_access_requests(path, requests)
            return updated

    request = AccessRequest(
        request_id=uuid.uuid4().hex[:12],
        user_id=int(user_id),
        chat_id=int(chat_id),
        username=username,
        full_name=full_name,
        phone_number=phone_number,
        requested_at=requested_at,
    )
    requests[request.request_id] = request
    save_access_requests(path, requests)
    return request


def get_access_request(path: Path, request_id: str) -> Optional[AccessRequest]:
    return load_access_requests(path).get(request_id)


def update_access_request_status(
    path: Path,
    request_id: str,
    *,
    status: str,
    reviewed_at: str,
    reviewed_by: Optional[int],
) -> Optional[AccessRequest]:
    requests = load_access_requests(path)
    current = requests.get(request_id)
    if current is None:
        return None

    updated = AccessRequest(
        request_id=current.request_id,
        user_id=current.user_id,
        chat_id=current.chat_id,
        username=current.username,
        full_name=current.full_name,
        phone_number=current.phone_number,
        requested_at=current.requested_at,
        status=status,
        reviewed_at=reviewed_at,
        reviewed_by=reviewed_by,
    )
    requests[request_id] = updated
    save_access_requests(path, requests)
    return updated


def format_access_request_for_admin(request: AccessRequest) -> str:
    username_text = "@{0}".format(request.username) if request.username else "не указан"
    return (
        "Новая заявка на доступ.\n"
        "Имя: {0}\n"
        "Телефон: {1}\n"
        "user_id: {2}\n"
        "chat_id: {3}\n"
        "username: {4}\n"
        "запрос: {5}"
    ).format(
        request.full_name or "не указано",
        request.phone_number or "не указан",
        request.user_id,
        request.chat_id,
        username_text,
        request.requested_at,
    )


__all__ = [
    "AccessRequest",
    "create_or_refresh_access_request",
    "format_access_request_for_admin",
    "get_access_request",
    "load_access_requests",
    "save_access_requests",
    "update_access_request_status",
]
