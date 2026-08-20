from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class EmbeddingModel(DomainModel):
    provider = models.CharField(max_length=255, blank=True, db_index=False)
    dimensions = models.BigIntegerField(default=0)
    version = models.BigIntegerField(default=0)
    max_tokens = models.BigIntegerField(default=0)
    enabled = models.BooleanField(default=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Embedding Model'
        verbose_name_plural = 'Embedding Model records'


class VectorDocument(DomainModel):
    source_type = models.CharField(max_length=255, blank=True, db_index=False)
    source_id = models.UUIDField(null=True, blank=True, db_index=True)
    namespace = models.ForeignKey('Namespace', on_delete=models.CASCADE, null=True, blank=True, related_name='vector_document_namespace_items')
    language = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Vector Document'
        verbose_name_plural = 'Vector Document records'


class VectorChunk(DomainModel):
    document = models.CharField(max_length=255, blank=True, db_index=False)
    chunk_index = models.CharField(max_length=255, blank=True, db_index=False)
    content = models.TextField(blank=True)
    token_count = models.BigIntegerField(default=0)
    embedding_model = models.ForeignKey('EmbeddingModel', on_delete=models.CASCADE, null=True, blank=True, related_name='vector_chunk_embedding_model_items')
    embedding_version = models.BigIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Vector Chunk'
        verbose_name_plural = 'Vector Chunk records'


class VectorIndex(DomainModel):
    provider = models.CharField(max_length=255, blank=True, db_index=False)
    index_name = models.CharField(max_length=255, blank=True, db_index=False)
    dimensions = models.BigIntegerField(default=0)
    distance_metric = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Vector Index'
        verbose_name_plural = 'Vector Index records'


class SearchHistory(DomainModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='vector_database_search_history_user')
    query = models.TextField(blank=True)
    namespace = models.ForeignKey('Namespace', on_delete=models.CASCADE, null=True, blank=True, related_name='search_history_namespace_items')
    results = models.JSONField(default=dict, blank=True)
    latency = models.BigIntegerField(default=0)

    class Meta(DomainModel.Meta):
        verbose_name = 'Search History'
        verbose_name_plural = 'Search History records'


class Namespace(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Namespace'
        verbose_name_plural = 'Namespace records'

