import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage

from src.graph_state import new_state
from src.nodes.respond import build_evidence_block, respond


class FakeLLM:
    def __init__(self) -> None:
        self.seen_prompt = ""

    def stream(self, messages, **_kwargs):
        self.seen_prompt = str(messages)
        yield AIMessage(content="NCC Mot (T001) ")
        yield AIMessage(content="gia tot nhat.")
        yield AIMessage(content="", usage_metadata={
            "input_tokens": 800, "output_tokens": 120, "total_tokens": 920,
        })


RANKED = [{
    "MaNCC": "T001", "TenNCC": "NCC Mot", "unit_price": 950_000,
    "total_price": 19_000_000, "ThoiGianGiao": 7, "MOQ": 10, "DiemUyTin": 4.5,
    "leverage_score": 0.82, "nguon_url": "https://vi.du/nguon",
    "simulated_fields": ["Gia", "MOQ"],
    "negotiation_strategy": {"muc_tieu_giam_gia": "5%"},
}]


def state_with(**kwargs):
    return {**new_state("Can 20 ghe van phong"), "ranked": RANKED,
            "verdict": {"passed": True, "violations": [], "claims": []}, **kwargs}


class EvidenceBlockTests(unittest.TestCase):
    def test_every_number_is_paired_with_its_supplier_and_source(self) -> None:
        block = build_evidence_block(state_with())
        self.assertIn("T001", block)
        self.assertIn("19000000", block)       # VND so thuan, khong dau phay
        self.assertIn("https://vi.du/nguon", block)
        self.assertIn("Gia", block)            # simulated_fields phai xuat hien

    def test_empty_ranked_produces_an_explicit_no_evidence_marker(self) -> None:
        block = build_evidence_block(state_with(ranked=[]))
        self.assertIn("KHONG CO", block.upper())


class RespondTests(unittest.TestCase):
    def test_counts_one_llm_call_and_the_reported_tokens(self) -> None:
        fake = FakeLLM()
        with patch("src.nodes.respond.get_llm", return_value=fake):
            out = respond(state_with())
        self.assertEqual(out["llm_calls"], 1)
        self.assertEqual(out["tokens_in"], 800)
        self.assertEqual(out["tokens_out"], 120)
        self.assertEqual(out["status"], "success")

    def test_streams_and_records_time_to_first_token(self) -> None:
        with patch("src.nodes.respond.get_llm", return_value=FakeLLM()):
            out = respond(state_with())
        self.assertEqual(out["answer"], "NCC Mot (T001) gia tot nhat.")
        self.assertIsInstance(out["ttft_ms"], float)
        self.assertGreaterEqual(out["ttft_ms"], 0)

    def test_evidence_is_put_into_the_prompt(self) -> None:
        fake = FakeLLM()
        with patch("src.nodes.respond.get_llm", return_value=fake):
            respond(state_with())
        self.assertIn("https://vi.du/nguon", fake.seen_prompt)

    def test_llm_failure_degrades_to_a_deterministic_answer(self) -> None:
        class Broken:
            def stream(self, *_a, **_k):
                raise RuntimeError("mang loi")

        with patch("src.nodes.respond.get_llm", return_value=Broken()):
            out = respond(state_with())
        # Van phai tra loi duoc tu bang chung, khong duoc bia va khong duoc sap
        self.assertIn("T001", out["answer"])
        self.assertEqual(out["status"], "success")
        self.assertEqual(out["llm_calls"], 0)

    def test_no_evidence_means_no_recommendation(self) -> None:
        with patch("src.nodes.respond.get_llm", return_value=FakeLLM()):
            out = respond(state_with(ranked=[]))
        self.assertEqual(out["status"], "graceful_fail")
        self.assertEqual(out["llm_calls"], 0)

    def test_list_shaped_chunk_content_is_flattened_not_crashed(self) -> None:
        # Gemini voi AFC bat co the tra content la list cac content-block thay
        # vi str thuan - phat hien qua goi that voi gemini-3.6-flash (Task 16).
        class ListContentLLM:
            def stream(self, messages, **_kwargs):
                yield AIMessage(content=[{"text": "NCC Mot "}])
                yield AIMessage(content=[{"text": "(T001) gia tot nhat."}])
                yield AIMessage(content="", usage_metadata={
                    "input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
                })

        with patch("src.nodes.respond.get_llm", return_value=ListContentLLM()):
            out = respond(state_with())
        self.assertEqual(out["answer"], "NCC Mot (T001) gia tot nhat.")
        self.assertEqual(out["status"], "success")
        self.assertEqual(out["llm_calls"], 1)


if __name__ == "__main__":
    unittest.main()
