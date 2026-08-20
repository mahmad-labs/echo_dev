from django.test import SimpleTestCase

from .embedding import feature_hash_embedding
from .vector_math import cosine_similarity


class VectorMathTests(SimpleTestCase):
    def test_embedding_is_normalized_and_deterministic(self):
        first = feature_hash_embedding("Echo enterprise search", dimensions=64)
        second = feature_hash_embedding("Echo enterprise search", dimensions=64)
        self.assertEqual(first, second)
        self.assertAlmostEqual(cosine_similarity(first, first), 1.0)
