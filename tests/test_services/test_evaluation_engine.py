"""Evaluation engine tests."""

import pytest

from app.services.evaluation_engine import EvaluationEngine, Verdict


class TestEvaluationEngine:
    """Test evaluation engine."""

    @pytest.fixture
    def engine(self):
        """Get evaluation engine with test thresholds."""
        return EvaluationEngine(
            correct_threshold=0.75,
            partial_threshold=0.50,
        )

    def test_evaluate_identical_answers(self, engine):
        """Test evaluating identical answers."""
        text = "The mitochondria is the powerhouse of the cell."
        result = engine.evaluate_answer(text, text)

        assert result.similarity_score > 0.95
        assert result.verdict == Verdict.CORRECT

    def test_evaluate_similar_answers(self, engine):
        """Test evaluating similar but not identical answers."""
        student = "Mitochondria produces energy for the cell."
        model = "The mitochondria is the powerhouse of the cell."
        result = engine.evaluate_answer(student, model)

        assert result.similarity_score >= 0.5
        assert result.verdict in [Verdict.CORRECT, Verdict.PARTIAL]

    def test_evaluate_different_answers(self, engine):
        """Test evaluating completely different answers."""
        student = "The sky is blue because of light scattering."
        model = "DNA replication occurs during the S phase."
        result = engine.evaluate_answer(student, model)

        assert result.similarity_score < 0.5
        assert result.verdict == Verdict.INCORRECT

    def test_evaluate_batch(self, engine):
        """Test batch evaluation."""
        student_texts = [
            "Water boils at 100 degrees Celsius.",
            "The Earth orbits the Sun.",
        ]
        model_texts = [
            "Water boils at 100 degrees Celsius at sea level.",
            "The Sun is at the center of our solar system.",
        ]

        results = engine.evaluate_batch(student_texts, model_texts)

        assert len(results) == 2
        assert all(r.verdict in Verdict for r in results)

    def test_verdict_thresholds(self, engine):
        """Test that verdict thresholds are applied correctly."""
        # Test correct threshold
        result = engine._determine_verdict(0.80)
        assert result == Verdict.CORRECT

        # Test partial threshold
        result = engine._determine_verdict(0.60)
        assert result == Verdict.PARTIAL

        # Test incorrect
        result = engine._determine_verdict(0.40)
        assert result == Verdict.INCORRECT
