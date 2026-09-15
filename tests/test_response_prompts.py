import unittest

from src.reasoning.prompts import (
    build_limits_messages,
    build_verified_response_messages,
)


class VerifiedResponsePromptTests(unittest.TestCase):
    def test_verified_context_preserves_unicode_and_source(self) -> None:
        verdict = {
            "passed": True,
            "violations": [],
            "claims": [{
                "claim": "NCC001.total_price",
                "value": 32_000_000,
                "supported": True,
                "evidence": {
                    "MaNCC": "NCC001",
                    "field": "total_price",
                    "nguon_url": "https://example.test/ncc001",
                },
            }],
        }

        messages = build_verified_response_messages(
            {"MaNCC": "NCC001", "explanation": "Phù hợp ngân sách"},
            verdict,
        )

        self.assertEqual([item["role"] for item in messages], ["system", "user"])
        self.assertIn("Phù hợp ngân sách", messages[1]["content"])
        self.assertIn("https://example.test/ncc001", messages[1]["content"])
        self.assertIn("simulated_fields", messages[0]["content"])
        self.assertIn("confirm_gate", messages[0]["content"])

    def test_failed_verdict_cannot_reach_response_prompt(self) -> None:
        with self.assertRaisesRegex(ValueError, "failed verdict"):
            build_verified_response_messages({}, {"passed": False, "claims": []})

    def test_uncited_claim_cannot_reach_response_prompt(self) -> None:
        verdict = {
            "passed": True,
            "claims": [{"claim": "NCC001.MOQ", "supported": True, "evidence": {}}],
        }

        with self.assertRaisesRegex(ValueError, "nguon_url"):
            build_verified_response_messages({}, verdict)


class LimitsPromptTests(unittest.TestCase):
    def test_limits_prompt_has_no_supplier_tool_instruction(self) -> None:
        messages = build_limits_messages("Tôi muốn mua ô tô", ["ghế văn phòng", "sofa"])

        self.assertIn("Tôi muốn mua ô tô", messages[1]["content"])
        self.assertIn("ghế văn phòng", messages[1]["content"])
        self.assertIn("không gọi tool", messages[0]["content"])


if __name__ == "__main__":
    unittest.main()
