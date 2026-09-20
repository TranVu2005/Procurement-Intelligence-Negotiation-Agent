import unittest

from src.logging_utils.tracer import redact

FAKE_GOOGLE_KEY = "AIza" + "x" * 35
FAKE_OPENROUTER_KEY = "sk-or-v1-" + "a" * 40


class RedactTests(unittest.TestCase):
    def test_top_level_secret_is_masked(self) -> None:
        self.assertEqual(redact({"api_key": "abc", "q": 1}), {"api_key": "***", "q": 1})

    def test_nested_dicts_and_lists_are_masked(self) -> None:
        payload = {"params": {"headers": {"Authorization": "Bearer x"}},
                   "items": [{"openrouter_api_key": "y"}, {"ok": 2}]}
        out = redact(payload)
        self.assertEqual(out["params"]["headers"]["Authorization"], "***")
        self.assertEqual(out["items"][0]["openrouter_api_key"], "***")
        self.assertEqual(out["items"][1], {"ok": 2})

    def test_key_shaped_strings_inside_free_text_are_masked(self) -> None:
        out = redact({"user_input": f"key cua toi la {FAKE_GOOGLE_KEY} nhe",
                      "note": FAKE_OPENROUTER_KEY})
        self.assertNotIn(FAKE_GOOGLE_KEY, out["user_input"])
        self.assertIn("***", out["user_input"])
        self.assertEqual(out["note"], "***")

    def test_input_is_not_mutated(self) -> None:
        payload = {"params": {"api_key": "abc"}}
        redact(payload)
        self.assertEqual(payload["params"]["api_key"], "abc")

    def test_ordinary_values_pass_through(self) -> None:
        payload = {"MaNCC": "NCC001", "Gia": 1_677_150, "tags": ["a", "b"]}
        self.assertEqual(redact(payload), payload)

    def test_product_url_slugs_are_not_mistaken_for_keys(self) -> None:
        url = "https://vi.du/san-pham/task-ban-lam-viec-go-tu-nhien-cao-cap-1m2"
        self.assertEqual(redact({"nguon_url": url}), {"nguon_url": url})


if __name__ == "__main__":
    unittest.main()
