from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class KnowledgeCollection(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Knowledge Collection'
        verbose_name_plural = 'Knowledge Collection records'


class KnowledgeCategory(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Knowledge Category'
        verbose_name_plural = 'Knowledge Category records'


class KnowledgeDocument(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Knowledge Document'
        verbose_name_plural = 'Knowledge Document records'


class DocumentSection(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Document Section'
        verbose_name_plural = 'Document Section records'


class ContentBlock(DomainModel):
    supported_types = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Content Block'
        verbose_name_plural = 'Content Block records'


class KnowledgeTag(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Knowledge Tag'
        verbose_name_plural = 'Knowledge Tag records'


class KnowledgeVersion(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Knowledge Version'
        verbose_name_plural = 'Knowledge Version records'


class KnowledgePermission(DomainModel):
    permissions = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Knowledge Permission'
        verbose_name_plural = 'Knowledge Permission records'


class KnowledgeComment(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Knowledge Comment'
        verbose_name_plural = 'Knowledge Comment records'


class KnowledgeAttachment(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Knowledge Attachment'
        verbose_name_plural = 'Knowledge Attachment records'

