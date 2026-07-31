from __future__ import annotations

import unittest

from uavguard.knowledge_base.fuzzy_matcher import score_candidates, similarity_score


class FuzzyMatcherTests(unittest.TestCase):
    def test_similarity_score_rewards_close_matches(self) -> None:
        score = similarity_score("DJI Mini 3", "Dji Mini3")
        self.assertGreater(score, 70)

    def test_score_candidates_orders_matches(self) -> None:
        matches = score_candidates(
            "mini 3",
            ["DJI Mini 3", "Autel Evo II", "Parrot Anafi"],
            limit=2,
        )
        self.assertEqual(matches[0][0], "DJI Mini 3")


if __name__ == "__main__":
    unittest.main()
