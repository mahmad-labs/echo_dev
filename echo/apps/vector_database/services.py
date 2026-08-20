from echo.common.services import DomainService

from .models import EmbeddingModel, VectorChunk, VectorIndex, SearchHistory, Namespace

class EmbeddingService(DomainService):
    model = EmbeddingModel

class ChunkService(DomainService):
    model = VectorChunk

class IndexingService(DomainService):
    model = VectorIndex

class RetrievalService(DomainService):
    model = SearchHistory

class SynchronizationService(DomainService):
    model = VectorIndex

class NamespaceService(DomainService):
    model = Namespace
