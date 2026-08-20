from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class Document(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Document'
        verbose_name_plural = 'Document records'


class DocumentMetadata(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Document Metadata'
        verbose_name_plural = 'Document Metadata records'


class DocumentContent(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Document Content'
        verbose_name_plural = 'Document Content records'


class DocumentPage(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Document Page'
        verbose_name_plural = 'Document Page records'


class DocumentVersion(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Document Version'
        verbose_name_plural = 'Document Version records'


class DocumentTag(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Document Tag'
        verbose_name_plural = 'Document Tag records'


class ProcessingJob(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Processing Job'
        verbose_name_plural = 'Processing Job records'

