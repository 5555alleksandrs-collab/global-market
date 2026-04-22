import tempfile
import unittest
from pathlib import Path

from competitor_price_monitor.access_requests import (
    create_or_refresh_access_request,
    format_access_request_for_admin,
    get_access_request,
    update_access_request_status,
)


class AccessRequestsTests(unittest.TestCase):
    def test_create_or_refresh_access_request_reuses_pending_request(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "requests.json"
            first = create_or_refresh_access_request(
                path,
                user_id=10,
                chat_id=20,
                username="pavel",
                full_name="Pavel",
                phone_number="+79000000000",
                requested_at="2026-03-30T12:00:00+03:00",
            )
            second = create_or_refresh_access_request(
                path,
                user_id=10,
                chat_id=20,
                username="pavel_new",
                full_name="Pavel Updated",
                phone_number="+79000000001",
                requested_at="2026-03-30T12:05:00+03:00",
            )

            self.assertEqual(first.request_id, second.request_id)
            self.assertEqual(second.phone_number, "+79000000001")
            self.assertEqual(second.full_name, "Pavel Updated")

    def test_update_access_request_status(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "requests.json"
            created = create_or_refresh_access_request(
                path,
                user_id=10,
                chat_id=20,
                username="pavel",
                full_name="Pavel",
                phone_number="+79000000000",
                requested_at="2026-03-30T12:00:00+03:00",
            )

            updated = update_access_request_status(
                path,
                created.request_id,
                status="approved",
                reviewed_at="2026-03-30T12:10:00+03:00",
                reviewed_by=99,
            )

            self.assertIsNotNone(updated)
            self.assertEqual(updated.status, "approved")
            self.assertEqual(updated.reviewed_by, 99)
            self.assertEqual(get_access_request(path, created.request_id).status, "approved")

    def test_format_access_request_for_admin_contains_main_fields(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "requests.json"
            created = create_or_refresh_access_request(
                path,
                user_id=10,
                chat_id=20,
                username="pavel",
                full_name="Pavel",
                phone_number="+79000000000",
                requested_at="2026-03-30T12:00:00+03:00",
            )

            text = format_access_request_for_admin(created)

            self.assertIn("Новая заявка на доступ.", text)
            self.assertIn("Телефон: +79000000000", text)
            self.assertIn("user_id: 10", text)
            self.assertIn("@pavel", text)


if __name__ == "__main__":
    unittest.main()
