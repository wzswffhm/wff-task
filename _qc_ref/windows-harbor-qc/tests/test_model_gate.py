import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_model_gate import evaluate


def run(score, statuses=("PASS",)):
    return {"validity": "VALID", "score": score,
            "cases": [{"id": f"case-{i}", "status": status} for i, status in enumerate(statuses)]}


class ModelGateTests(unittest.TestCase):
    def evidence(self, qwen_scores=(0, 0, 0), opus_scores=(1, 1, 1), qwen_status=("PASS",), opus_status=("PASS",)):
        return {"qwen": [run(s, qwen_status) for s in qwen_scores],
                "opus": [run(s, opus_status) for s in opus_scores],
                "glm": [run(1)], "kimi": [run(0)]}

    def test_opus_score_sum_wins(self):
        result = evaluate(self.evidence())
        self.assertTrue(result["pass"], result["errors"])

    def test_equal_nonzero_scores_fail(self):
        result = evaluate(self.evidence(qwen_scores=(1, 0, 0), opus_scores=(0, 1, 0)))
        self.assertFalse(result["pass"])

    def test_equal_zero_uses_strict_testcase_pass_sum(self):
        result = evaluate(self.evidence(qwen_scores=(0, 0, 0), opus_scores=(0, 0, 0),
                                        qwen_status=("FAIL",), opus_status=("PASS",)))
        self.assertTrue(result["pass"], result["errors"])

    def test_invalid_run_cannot_be_counted_as_zero(self):
        evidence = self.evidence()
        evidence["qwen"][0] = {"validity": "INVALID", "score": None, "cases": []}
        result = evaluate(evidence)
        self.assertFalse(result["pass"])


if __name__ == "__main__":
    unittest.main()
