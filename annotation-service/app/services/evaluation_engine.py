"""Semantic similarity evaluation engine."""
from dataclasses import dataclass
from enum import Enum

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Verdict(str, Enum):
    """Verdict for an evaluated answer."""

    CORRECT = "correct"
    PARTIAL = "partial"
    INCORRECT = "incorrect"


@dataclass
class EvaluationScore:
    """Evaluation result for a single answer."""

    similarity_score: float
    verdict: Verdict
    confidence: float
    model_answer_reference: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "similarity_score": self.similarity_score,
            "verdict": self.verdict.value,
            "confidence": self.confidence,
            "model_answer_reference": self.model_answer_reference,
        }


class EvaluationEngine:
    """Semantic similarity evaluation engine using sentence transformers."""

    def __init__(
        self,
        model_name: str | None = None,
        correct_threshold: float | None = None,
        partial_threshold: float | None = None,
    ):
        """Initialize evaluation engine.

        Args:
            model_name: Name of the sentence transformer model
            correct_threshold: Threshold for correct verdict (>= this is correct)
            partial_threshold: Threshold for partial verdict (>= this is partial)
        """
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self.correct_threshold = correct_threshold or settings.correct_threshold
        self.partial_threshold = partial_threshold or settings.partial_threshold

        self._model: SentenceTransformer | None = None
        logger.info(
            "Initialized evaluation engine",
            model=self.model_name,
            correct_threshold=self.correct_threshold,
            partial_threshold=self.partial_threshold,
        )

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the sentence transformer model."""
        if self._model is None:
            logger.info("Loading sentence transformer model", model=self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def evaluate_answer(
        self,
        student_text: str,
        model_text: str,
    ) -> EvaluationScore:
        """Evaluate a student answer against a model answer.

        Args:
            student_text: Student's answer text
            model_text: Model answer text

        Returns:
            Evaluation score with similarity and verdict
        """
        # Compute embeddings
        embeddings = self.model.encode([student_text, model_text])
        student_embedding = embeddings[0]
        model_embedding = embeddings[1]

        # Compute cosine similarity
        similarity = self._cosine_similarity(student_embedding, model_embedding)

        # Determine verdict
        verdict = self._determine_verdict(similarity)

        # Confidence based on similarity distance from thresholds
        confidence = self._compute_confidence(similarity)

        return EvaluationScore(
            similarity_score=float(similarity),
            verdict=verdict,
            confidence=confidence,
            model_answer_reference=model_text,
        )

    def evaluate_batch(
        self,
        student_texts: list[str],
        model_texts: list[str],
    ) -> list[EvaluationScore]:
        """Evaluate multiple answers in batch for efficiency.

        Args:
            student_texts: List of student answer texts
            model_texts: List of corresponding model answer texts

        Returns:
            List of evaluation scores
        """
        if len(student_texts) != len(model_texts):
            raise ValueError("Student and model text lists must have same length")

        if not student_texts:
            return []

        # Encode all texts together for efficiency
        all_texts = student_texts + model_texts
        all_embeddings = self.model.encode(all_texts)

        n = len(student_texts)
        student_embeddings = all_embeddings[:n]
        model_embeddings = all_embeddings[n:]

        results = []
        for i in range(n):
            similarity = self._cosine_similarity(
                student_embeddings[i],
                model_embeddings[i],
            )
            verdict = self._determine_verdict(similarity)
            confidence = self._compute_confidence(similarity)

            results.append(
                EvaluationScore(
                    similarity_score=float(similarity),
                    verdict=verdict,
                    confidence=confidence,
                    model_answer_reference=model_texts[i],
                )
            )

        logger.info(
            "Batch evaluated answers",
            count=len(results),
            verdicts={v.value: sum(1 for r in results if r.verdict == v) for v in Verdict},
        )

        return results

    def _cosine_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray,
    ) -> float:
        """Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score (0 to 1)
        """
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)
        # Ensure similarity is in [0, 1] range
        return max(0.0, min(1.0, float(similarity)))

    def _determine_verdict(self, similarity: float) -> Verdict:
        """Determine verdict based on similarity score.

        Args:
            similarity: Similarity score (0 to 1)

        Returns:
            Verdict enum value
        """
        if similarity >= self.correct_threshold:
            return Verdict.CORRECT
        elif similarity >= self.partial_threshold:
            return Verdict.PARTIAL
        else:
            return Verdict.INCORRECT

    def _compute_confidence(self, similarity: float) -> float:
        """Compute confidence score based on similarity.

        Higher confidence when similarity is far from thresholds.

        Args:
            similarity: Similarity score

        Returns:
            Confidence score (0 to 1)
        """
        # Distance to nearest threshold
        distances = [
            abs(similarity - self.correct_threshold),
            abs(similarity - self.partial_threshold),
        ]
        min_distance = min(distances)

        # Convert distance to confidence (farther = more confident)
        # Max distance is 0.5 (from 0.5 to either 0 or 1)
        confidence = min(1.0, min_distance / 0.25 + 0.5)
        return confidence
