import tempfile
import unittest
from pathlib import Path

from competitor_price_monitor.access_control import (
    add_allowed_chat,
    add_allowed_user,
    build_access_config,
    format_access_list,
    format_identity_message,
    is_authorized_chat,
    is_authorized_for_bot,
    load_access_store,
    merge_access_configs,
    parse_id_list,
    requires_explicit_access,
    remove_allowed_chat,
    remove_allowed_user,
    save_access_store,
)


class AccessControlTests(unittest.TestCase):
    def test_parse_id_list_supports_commas_and_newlines(self):
        self.assertEqual(parse_id_list("123, 456\n789"), frozenset({123, 456, 789}))

    def test_is_authorized_chat_allows_everyone_when_config_empty(self):
        config = build_access_config()
        self.assertTrue(is_authorized_chat(chat_id=100, user_id=200, config=config))

    def test_is_authorized_chat_requires_both_dimensions_when_both_configured(self):
        config = build_access_config(allowed_user_ids=[10], allowed_chat_ids=[20])
        self.assertTrue(is_authorized_chat(chat_id=20, user_id=10, config=config))
        self.assertFalse(is_authorized_chat(chat_id=21, user_id=10, config=config))
        self.assertFalse(is_authorized_chat(chat_id=20, user_id=11, config=config))

    def test_requires_explicit_access_when_admin_exists(self):
        self.assertTrue(
            requires_explicit_access(
                build_access_config(),
                build_access_config(allowed_user_ids=[999]),
            )
        )

    def test_is_authorized_for_bot_denies_strangers_when_only_admin_is_configured(self):
        access_config = build_access_config()
        admin_config = build_access_config(allowed_user_ids=[999])

        self.assertTrue(
            is_authorized_for_bot(
                chat_id=100,
                user_id=999,
                access_config=access_config,
                admin_config=admin_config,
            )
        )
        self.assertFalse(
            is_authorized_for_bot(
                chat_id=100,
                user_id=200,
                access_config=access_config,
                admin_config=admin_config,
            )
        )

    def test_is_authorized_for_bot_uses_access_allowlist_for_non_admins(self):
        access_config = build_access_config(allowed_user_ids=[200])
        admin_config = build_access_config(allowed_user_ids=[999])

        self.assertTrue(
            is_authorized_for_bot(
                chat_id=100,
                user_id=200,
                access_config=access_config,
                admin_config=admin_config,
            )
        )
        self.assertFalse(
            is_authorized_for_bot(
                chat_id=100,
                user_id=201,
                access_config=access_config,
                admin_config=admin_config,
            )
        )

    def test_merge_access_configs_unions_ids(self):
        merged = merge_access_configs(
            build_access_config(allowed_user_ids=[10], allowed_chat_ids=[20]),
            build_access_config(allowed_user_ids=[11], allowed_chat_ids=[21]),
        )
        self.assertEqual(merged.allowed_user_ids, frozenset({10, 11}))
        self.assertEqual(merged.allowed_chat_ids, frozenset({20, 21}))

    def test_access_store_roundtrip_and_mutations(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "access.json"
            config = build_access_config()
            config = add_allowed_user(config, 10)
            config = add_allowed_chat(config, -1001)
            save_access_store(config, path)

            loaded = load_access_store(path)
            self.assertEqual(loaded.allowed_user_ids, frozenset({10}))
            self.assertEqual(loaded.allowed_chat_ids, frozenset({-1001}))

            loaded = remove_allowed_user(loaded, 10)
            loaded = remove_allowed_chat(loaded, -1001)
            self.assertFalse(loaded.allowed_user_ids)
            self.assertFalse(loaded.allowed_chat_ids)

    def test_format_access_list(self):
        text = format_access_list(build_access_config(allowed_user_ids=[10], allowed_chat_ids=[20]))
        self.assertIn("allowed_user_ids: 10", text)
        self.assertIn("allowed_chat_ids: 20", text)

    def test_format_identity_message_contains_ids_and_access(self):
        message = format_identity_message(
            user_id=10,
            chat_id=20,
            username="pavel",
            chat_type="private",
            authorized=True,
        )
        self.assertIn("user_id: 10", message)
        self.assertIn("chat_id: 20", message)
        self.assertIn("@pavel", message)
        self.assertIn("текущий доступ: разрешён", message)


if __name__ == "__main__":
    unittest.main()
