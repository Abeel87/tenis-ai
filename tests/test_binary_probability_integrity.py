import copy
import unittest
from unittest.mock import Mock, patch

from backend import symphony2_engine as engine
from backend import symphony2_learning as learning


class BinaryProbabilityIntegrityTests(unittest.TestCase):
    def test_exact_offer_publishes_coherent_pair_without_rewriting_raw_evidence(self):
        model = Mock(ready=True)
        model.predict_diagnostics.side_effect = [
            {"raw": raw, "calibrated": raw, "final": raw,
             "support": 664, "reliability": 1.0, "market_calibrator": False}
            for raw in [0.5825, 0.6417]
        ]
        match = {"p1": "Ryo Tabata", "p2": "Tristan Boyer", "superbet_market_v91": {
            "operator": "superbet.pl", "operator_verified": True, "status": "VERIFIED",
            "canonical_selections": [{"market": "any_set_to_nil", "pick": pick,
                "operator_available": True, "operator_line_verified": True}
                for pick in ["yes", "no"]],
        }}
        before = copy.deepcopy(match)
        rows = engine._score_offer(match, model, [])
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(row["operator_model_probability"] for row in rows), 100.0)
        self.assertEqual({r["pick"]: r["raw_model_probability"] for r in rows}, {"yes": 58.25, "no": 64.17})
        self.assertTrue(all(row["state_probability"] is None for row in rows))
        self.assertEqual(match, before)

    def test_reported_tabata_boyer_pair_is_complementary(self):
        rows = [
            {"market": "any_set_to_nil", "pick": "yes", "operator_model_probability": 99.98},
            {"market": "any_set_to_nil", "pick": "no", "operator_model_probability": 99.96},
        ]
        result = engine._cohere_exclusive_probabilities(rows)
        self.assertAlmostEqual(sum(r["operator_model_probability"] for r in result), 100.0)
        self.assertTrue(all(r["operator_model_probability"] < 100 for r in result))
        self.assertEqual([r["operator_model_probability_pre_coherence"] for r in result], [99.98, 99.96])

    def test_binary_pairs_keep_market_player_and_checkpoint_scopes(self):
        rows = [
            {"market": "set1_tiebreak", "pick": "tak", "operator_model_probability": 12.0},
            {"market": "set1_tiebreak", "pick": "nie", "operator_model_probability": 88.0},
            {"market": "p1_wins_a_set", "pick": "yes", "player": "A", "operator_model_probability": 80.0},
            {"market": "p1_wins_a_set", "pick": "no", "player": "B", "operator_model_probability": 60.0},
            {"market": "any_set_to_nil", "pick": "yes", "checkpoint": 1, "operator_model_probability": 11.0},
            {"market": "any_set_to_nil", "pick": "no", "checkpoint": 2, "operator_model_probability": 90.0},
        ]
        before = copy.deepcopy(rows)
        result = engine._cohere_exclusive_probabilities(rows)
        self.assertEqual([r["operator_model_probability"] for r in result[:2]], [12.0, 88.0])
        self.assertTrue(all(r.get("probability_coherence") for r in result[:2]))
        self.assertEqual(result[2:], before[2:])

    def test_incomplete_duplicate_unknown_and_missing_binary_rows_stay_unchanged(self):
        for rows in [
            [{"market": "any_set_to_nil", "pick": "yes", "operator_model_probability": 12.0}],
            [{"market": "any_set_to_nil", "pick": p, "operator_model_probability": v} for p, v in [("yes", 12), ("no", None)]],
            [{"market": "any_set_to_nil", "pick": p, "operator_model_probability": 20} for p in ["yes", "yes"]],
            [{"market": "unknown_binary", "pick": p, "operator_model_probability": 20} for p in ["yes", "no"]],
        ]:
            before = copy.deepcopy(rows)
            self.assertEqual(engine._cohere_exclusive_probabilities(rows), before)

    def test_rank_reversing_calibrator_is_rejected_even_when_brier_improves(self):
        candidate = learning.PlattCalibrator(a=-1.992322, b=9.001566, fitted=True)
        # A near-all-hit later window can reward inversion; it must not reverse
        # the meaning/order of the upstream hit probability.
        with patch.object(learning.PlattCalibrator, "fit", return_value=candidate):
            chosen, info = learning._accepted_calibrator(
                [0.6, 0.7] * 20, [1, 0] * 20,
                [0.6] * 45, [1] * 43 + [0] * 2,
            )
        self.assertLess(info["calibrated_brier"], info["raw_brier"])
        self.assertFalse(info["accepted"])
        self.assertFalse(chosen.fitted)
        self.assertEqual(info["rejection_reason"], "NON_MONOTONIC_CALIBRATION")
        self.assertEqual(chosen.predict(0.6), 0.6)

    def test_valid_monotonic_calibration_can_still_be_accepted(self):
        candidate = learning.PlattCalibrator(a=2.0, b=0.0, fitted=True)
        with patch.object(learning.PlattCalibrator, "fit", return_value=candidate):
            chosen, info = learning._accepted_calibrator(
                [0.7, 0.3] * 20, [1, 0] * 20,
                [0.7, 0.3] * 10, [1, 0] * 10,
            )
        self.assertTrue(info["accepted"])
        self.assertTrue(chosen.fitted)


if __name__ == "__main__":
    unittest.main()
