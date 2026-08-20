from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class Conversation(DomainModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='chat_conversation_user')
    conversation_type = models.CharField(max_length=255, blank=True, db_index=False)
    current_model = models.CharField(max_length=255, blank=True, db_index=False)
    system_prompt = models.TextField(blank=True)
    temperature = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    max_tokens = models.BigIntegerField(default=0)
    is_pinned = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    is_shared = models.BooleanField(default=False)
    share_token = models.CharField(max_length=255, blank=True, db_index=False)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversation records'


class Message(DomainModel):
    conversation = models.ForeignKey('Conversation', on_delete=models.CASCADE, null=True, blank=True, related_name='message_conversation_items')
    sender = models.CharField(max_length=255, blank=True, db_index=False)
    role = models.CharField(max_length=255, blank=True, db_index=False)
    content = models.TextField(blank=True)
    rendered_content = models.TextField(blank=True)
    token_count = models.BigIntegerField(default=0)
    message_type = models.TextField(blank=True)
    parent_message = models.TextField(blank=True)
    edited = models.CharField(max_length=255, blank=True, db_index=False)
    edited_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Message'
        verbose_name_plural = 'Message records'


class MessageAttachment(DomainModel):
    message = models.ForeignKey('Message', on_delete=models.CASCADE, null=True, blank=True, related_name='message_attachment_message_items')
    file_reference = models.UUIDField(null=True, blank=True, db_index=True)
    attachment_type = models.CharField(max_length=255, blank=True, db_index=False)
    mime_type = models.CharField(max_length=255, blank=True, db_index=False)
    file_size = models.BigIntegerField(default=0)
    checksum = models.TextField(blank=True)
    processing_status = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Message Attachment'
        verbose_name_plural = 'Message Attachment records'


class MessageReaction(DomainModel):
    message = models.ForeignKey('Message', on_delete=models.CASCADE, null=True, blank=True, related_name='message_reaction_message_items')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='chat_message_reaction_user')
    reaction = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Message Reaction'
        verbose_name_plural = 'Message Reaction records'


class ConversationFolder(DomainModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='chat_conversation_folder_user')
    color = models.CharField(max_length=255, blank=True, db_index=False)
    icon = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Conversation Folder'
        verbose_name_plural = 'Conversation Folder records'


class ConversationTag(DomainModel):
    conversation = models.ForeignKey('Conversation', on_delete=models.CASCADE, null=True, blank=True, related_name='conversation_tag_conversation_items')
    tag = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Conversation Tag'
        verbose_name_plural = 'Conversation Tag records'


class SharedConversation(DomainModel):
    conversation = models.ForeignKey('Conversation', on_delete=models.CASCADE, null=True, blank=True, related_name='shared_conversation_conversation_items')
    token = models.CharField(max_length=255, blank=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    view_count = models.BigIntegerField(default=0)

    class Meta(DomainModel.Meta):
        verbose_name = 'Shared Conversation'
        verbose_name_plural = 'Shared Conversation records'


class ChatSettings(DomainModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='chat_chat_settings_user')
    default_model = models.CharField(max_length=255, blank=True, db_index=False)
    default_temperature = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    streaming_enabled = models.BooleanField(default=False)
    markdown_enabled = models.BooleanField(default=False)
    code_highlighting = models.BooleanField(default=False)
    auto_title = models.BooleanField(default=False)
    auto_save = models.BooleanField(default=False)
    auto_memory = models.BooleanField(default=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Chat Settings'
        verbose_name_plural = 'Chat Settings records'


class StreamingSession(DomainModel):
    conversation = models.ForeignKey('Conversation', on_delete=models.CASCADE, null=True, blank=True, related_name='streaming_session_conversation_items')
    message = models.ForeignKey('Message', on_delete=models.CASCADE, null=True, blank=True, related_name='streaming_session_message_items')
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True, db_index=True)
    latency = models.BigIntegerField(default=0)
    tokens_generated = models.BigIntegerField(default=0)

    class Meta(DomainModel.Meta):
        verbose_name = 'Streaming Session'
        verbose_name_plural = 'Streaming Session records'

