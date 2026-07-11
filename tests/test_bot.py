import tempfile
import unittest
from pathlib import Path

import bot


class BotTests(unittest.TestCase):
    def test_parse_directives_filters_other_users_and_preserves_order(self):
        messages = [
            {"user": "OWNER", "ts": "2.0", "text": "深掘り: USD"},
            {"user": "OTHER", "ts": "1.5", "text": "除外: Blender"},
            {"user": "OWNER", "ts": "1.0", "text": "方針：Houdiniを優先"},
        ]
        self.assertEqual(
            bot.parse_directives(messages, "OWNER"),
            [
                ("方針", "Houdiniを優先", "1.0"),
                ("深掘り", "USD", "2.0"),
            ],
        )

    def test_extract_output_text(self):
        response = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "digest"}],
                }
            ]
        }
        self.assertEqual(bot.extract_output_text(response), "digest")

    def test_state_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            state = bot.load_state(path)
            state["guidance"].append("一次情報優先")
            bot.save_state(state, path)
            self.assertEqual(bot.load_state(path)["guidance"], ["一次情報優先"])


if __name__ == "__main__":
    unittest.main()
