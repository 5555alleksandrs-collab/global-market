"""
Клиент официального WB Seller API.
Документация: https://openapi.wildberries.ru/

ВАЖНО: Авто-бронирование слотов через официальный API.
Эндпоинты для поставок: /api/v3/supplies/*
"""

from __future__ import annotations

import logging
import asyncio
from datetime import datetime, timedelta, date
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

WB_API_BASE = "https://supplies-api.wildberries.ru"
WB_STAT_BASE = "https://statistics-api.wildberries.ru"

# Коды типов поставок в API WB
SUPPLY_TYPE_MAP = {
    "box": "QRsupplies",
    "pallet": "MonoPallet",
    "supersafe": "Oversize",
}


class WBApiError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"WB API {status}: {message}")


class WBApiClient:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }

    async def _get(self, url: str, params: dict = None) -> dict | list:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self.headers, params=params)
        if resp.status_code not in (200, 201):
            raise WBApiError(resp.status_code, resp.text[:300])
        return resp.json()

    async def _post(self, url: str, json: dict = None) -> dict | list:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=self.headers, json=json or {})
        if resp.status_code not in (200, 201):
            raise WBApiError(resp.status_code, resp.text[:300])
        return resp.json()

    async def _patch(self, url: str, params: dict = None) -> dict | list:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(url, headers=self.headers, params=params)
        if resp.status_code not in (200, 201):
            raise WBApiError(resp.status_code, resp.text[:300])
        return resp.json()

    # ─── СКЛАДЫ ───────────────────────────────────────────────────────────────

    async def get_warehouses(self) -> list[dict]:
        """Список всех складов WB с коэффициентами приёмки."""
        data = await self._get(f"{WB_API_BASE}/api/v1/warehouses")
        return data if isinstance(data, list) else data.get("result", [])

    async def get_acceptance_coefficients(
        self,
        warehouse_ids: list[int] = None,
    ) -> list[dict]:
        """
        Коэффициенты приёмки по складам.
        Возвращает список: [{warehouseID, date, coefficient, boxTypeName}, ...]
        """
        params = {}
        if warehouse_ids:
            params["warehouseIDs"] = ",".join(map(str, warehouse_ids))
        data = await self._get(f"{WB_API_BASE}/api/v1/acceptance/coefficients", params)
        return data if isinstance(data, list) else []

    # ─── ПОСТАВКИ (SUPPLIES) ──────────────────────────────────────────────────

    async def get_supplies(self, status: str = "OPEN") -> list[dict]:
        """Список поставок. status: OPEN | CLOSED | AWAIT."""
        data = await self._get(
            f"{WB_API_BASE}/api/v3/supplies",
            params={"limit": 1000, "next": 0, "status": status},
        )
        return data.get("supplies", [])

    async def create_supply(self, name: str) -> dict:
        """Создать новую поставку (черновик)."""
        return await self._post(f"{WB_API_BASE}/api/v3/supplies", {"name": name})

    async def get_supply_orders(self, supply_id: str) -> list[dict]:
        """Список заказов в поставке."""
        data = await self._get(f"{WB_API_BASE}/api/v3/supplies/{supply_id}/orders")
        return data.get("orders", [])

    async def book_supply_timeslot(
        self,
        supply_id: str,
        warehouse_id: int,
        supply_date: str,
    ) -> dict:
        """
        Записать поставку на склад (тайм-слот).
        supply_date: строка вида "2024-09-05T00:00:00Z"
        """
        return await self._patch(
            f"{WB_API_BASE}/api/v3/supplies/{supply_id}/deliver",
            params={
                "warehouseID": warehouse_id,
                "supplyDate": supply_date,
            },
        )

    async def deliver_supply(self, supply_id: str) -> dict:
        """Передать поставку в доставку."""
        return await self._patch(f"{WB_API_BASE}/api/v3/supplies/{supply_id}/deliver")

    # ─── ПОИСК СЛОТОВ ─────────────────────────────────────────────────────────

    async def find_available_slots(
        self,
        warehouse_id: int,
        supply_type: str,
        date_from: date,
        date_to: date,
        max_coef: int,
    ) -> list[dict]:
        """
        Ищет доступные слоты (коэффициент <= max_coef) в диапазоне дат.
        Возвращает список подходящих слотов: [{date, coefficient, warehouseID}, ...]
        """
        coefficients = await self.get_acceptance_coefficients([warehouse_id])

        suitable = []
        for entry in coefficients:
            if entry.get("warehouseID") != warehouse_id:
                continue

            # Фильтр по типу поставки
            box_type = entry.get("boxTypeName", "").lower()
            if supply_type == "box" and "короб" not in box_type and "qr" not in box_type:
                continue
            if supply_type == "pallet" and "паллет" not in box_type and "mono" not in box_type:
                continue
            if supply_type == "supersafe" and "суперсейф" not in box_type and "oversize" not in box_type:
                continue

            # Фильтр по дате
            slot_date_str = entry.get("date", "")
            if not slot_date_str:
                continue
            try:
                slot_date = datetime.fromisoformat(slot_date_str.replace("Z", "+00:00")).date()
            except ValueError:
                continue
            if not (date_from <= slot_date <= date_to):
                continue

            # Фильтр по коэффициенту (−1 = закрыт)
            coef = entry.get("coefficient", -1)
            if coef < 0:
                continue
            if coef > max_coef:
                continue

            suitable.append({
                "date": slot_date.isoformat(),
                "coefficient": coef,
                "warehouseID": warehouse_id,
                "boxTypeName": entry.get("boxTypeName"),
            })

        # Сортируем по дате, потом по коэффициенту
        suitable.sort(key=lambda x: (x["date"], x["coefficient"]))
        return suitable

    # ─── ПЕРЕРАСПРЕДЕЛЕНИЕ ────────────────────────────────────────────────────

    async def get_stock_by_warehouse(self, date_from: str = None) -> list[dict]:
        """
        Остатки по складам через Statistics API.
        date_from: дата в формате 'YYYY-MM-DD'
        """
        if not date_from:
            date_from = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        data = await self._get(
            f"{WB_STAT_BASE}/api/v1/supplier/stocks",
            params={"dateFrom": date_from},
        )
        return data if isinstance(data, list) else []

    async def create_redistribution(
        self,
        article: str,
        from_warehouse_id: int,
        to_warehouse_id: int,
        quantity: int,
    ) -> dict:
        """
        Создать задачу на перераспределение остатков.
        ВНИМАНИЕ: этот эндпоинт доступен не всем продавцам — нужна квота WB.
        """
        payload = {
            "article": article,
            "fromWarehouseId": from_warehouse_id,
            "toWarehouseId": to_warehouse_id,
            "quantity": quantity,
        }
        return await self._post(f"{WB_API_BASE}/api/v1/stocks/redistribute", payload)

    # ─── УТИЛИТЫ ──────────────────────────────────────────────────────────────

    async def check_token(self) -> bool:
        """Проверяет валидность токена."""
        try:
            await self.get_warehouses()
            return True
        except WBApiError:
            return False
