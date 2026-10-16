import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_model_gate import evaluate


IDENTITY = {"task_id": "demo", "task_version": "1.0.0", "task_hash": "a" * 64}


def run(run_id, score, statuses=("PASS",), **overrides):
    value = {
        "run_id": run_id,
        "validity": "VALID",
        "score": score,
        "cases": [{"id": f"case-{i}", "status": status} for i, status in enumerate(statuses)],
        **IDENTITY,
    }
    value.update(overrides)
    return value


class ModelGateTests(unittest.TestCase):
    def evidence(self, qwen_scores=(0, 0, 0), opus_scores=(1, 1, 1)):
        return {
            "task": dict(IDENTITY),
            "models": {
                "qwen": [run(f"q{i}", score) for i, score in enumerate(qwen_scores)],
                "opus": [run(f"o{i}", score) for i, score in enumerate(opus_scores)],
            },
        }

    def test_opus_score_sum_wins(self):
        result = evaluate(self.evidence())
        self.assertTrue(result["pass"], result["errors"])

    def test_equal_nonzero_scores_fail(self):
        result = evaluate(self.evidence((1, 0, 0), (0, 1, 0)))
        self.assertFalse(result["pass"])

    def test_equal_nonzero_scores_fail_even_when_opus_testcases_are_better(self):
        evidence = self.evidence((1, 0, 0), (0, 1, 0))
        for item in evidence["models"]["qwen"]:
            item["cases"] = [
                {"id": "case-0", "status": "PASS"},
                {"id": "case-1", "status": "FAIL"},
            ]
        evidence["models"]["opus"][0]["cases"] = [
            {"id": "case-0", "status": "PASS"},
            {"id": "case-1", "status": "PASS"},
        ]
        for item in evidence["models"]["opus"][1:]:
            item["cases"] = [
                {"id": "case-0", "status": "PASS"},
                {"id": "case-1", "status": "FAIL"},
            ]
        result = evaluate(evidence)
        self.assertFalse(result["pass"])
        self.assertTrue(result["stats"]["distinction"]["opus_testcase_advantage"])
        self.assertFalse(result["stats"]["distinction"]["testcase_tiebreak_pass"])

    def test_all_models_valid_zero_rejects_qwen_opus_tie(self):
        evidence = self.evidence((0, 0, 0), (0, 0, 0))
        for item in evidence["models"]["qwen"] + evidence["models"]["opus"]:
            item["cases"][0]["status"] = "FAIL"
        result = evaluate(evidence)
        self.assertFalse(result["pass"])
        self.assertTrue(result["stats"]["distinction"]["all_models_zero"])
        self.assertFalse(result["stats"]["distinction"]["all_models_zero_exception"])

    def test_qwen_score_above_opus_fails_even_with_testcase_advantage(self):
        result = evaluate(self.evidence((1, 1, 0), (1, 0, 0)))
        self.assertFalse(result["pass"])

    def test_qwen_opus_zero_tie_still_fails_without_other_models(self):
        # 放宽 GLM/Kimi 后仍必须拒绝 Qwen/Opus 的零分平局。
        evidence = self.evidence((0, 0, 0), (0, 0, 0))
        result = evaluate(evidence)
        self.assertFalse(result["pass"])
        self.assertTrue(result["stats"]["distinction"]["score_tie"])

    def test_qwen_opus_full_score_is_rejected(self):
        result = evaluate(self.evidence((1, 1, 1), (1, 1, 1)))
        self.assertFalse(result["pass"])
        self.assertTrue(result["stats"]["distinction"]["qwen_opus_full_score"])
        self.assertTrue(any("both full-score" in error for error in result["errors"]))

    def test_qwen_opus_full_score_is_rejected_even_with_better_opus_testcases(self):
        evidence = self.evidence((1, 1, 1), (1, 1, 1))
        for item in evidence["models"]["qwen"]:
            item["cases"] = [
                {"id": "case-0", "status": "PASS"},
                {"id": "case-1", "status": "FAIL"},
            ]
        for item in evidence["models"]["opus"]:
            item["cases"] = [
                {"id": "case-0", "status": "PASS"},
                {"id": "case-1", "status": "PASS"},
            ]
        result = evaluate(evidence)
        self.assertFalse(result["pass"])
        self.assertTrue(result["stats"]["distinction"]["qwen_opus_full_score"])

    def test_primary_models_full_score_is_rejected_and_reported(self):
        # 放宽后只剩 Qwen/Opus，全满分与 qwen_opus_full_score 等价。
        evidence = self.evidence((1, 1, 1), (1, 1, 1))
        result = evaluate(evidence)
        self.assertFalse(result["pass"])
        self.assertTrue(result["stats"]["distinction"]["qwen_opus_full_score"])

    def test_glm_and_kimi_are_no_longer_required(self):
        # 甲方 2026-10-15 放宽：缺 GLM/Kimi 不再导致门禁失败。
        evidence = self.evidence()
        result = evaluate(evidence)
        self.assertTrue(result["pass"], result["errors"])

    def test_invalid_run_cannot_be_counted_as_zero(self):
        evidence = self.evidence()
        evidence["models"]["qwen"][0]["validity"] = "INVALID"
        result = evaluate(evidence)
        self.assertFalse(result["pass"])

    def test_task_hash_mismatch_fails(self):
        evidence = self.evidence()
        evidence["models"]["opus"][0]["task_hash"] = "b" * 64
        self.assertFalse(evaluate(evidence)["pass"])

    def test_duplicate_run_id_fails(self):
        evidence = self.evidence()
        evidence["models"]["opus"][0]["run_id"] = "q0"
        self.assertFalse(evaluate(evidence)["pass"])


if __name__ == "__main__":
    unittest.main()
