# Model Catalog

Echo contains 189 concrete Django model states across 24 domain applications. Models based on `DomainModel` also inherit the shared UUID, ownership, timestamps, name/title/description/status, and extensible data fields. The catalog below is generated from the current source declarations so orchestration, voice, browser, and desktop-control fields remain aligned with the implementation.
Generated source declarations listed: 189.

## `agent_manager`

### `Agent`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |
| `identifier` | `CharField` | `max_length=96, blank=True, db_index=True` |
| `version` | `CharField` | `max_length=32, default='1'` |
| `capabilities` | `JSONField` | `default=list, blank=True` |
| `required_tools` | `JSONField` | `default=list, blank=True` |
| `required_permissions` | `JSONField` | `default=list, blank=True` |
| `input_schema` | `JSONField` | `default=dict, blank=True` |
| `output_schema` | `JSONField` | `default=dict, blank=True` |
| `available` | `BooleanField` | `default=True, db_index=True` |
| `health_status` | `CharField` | `max_length=32, default='healthy', db_index=True` |
| `last_health_check` | `DateTimeField` | `null=True, blank=True, db_index=True` |

### `AgentCapability`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `AgentTask`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |
| `agent` | `ForeignKey` | `on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks'` |
| `parent_task` | `ForeignKey` | `on_delete=models.SET_NULL, null=True, blank=True, related_name='child_tasks'` |
| `conversation` | `ForeignKey` | `on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_tasks'` |
| `project` | `ForeignKey` | `on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_tasks'` |
| `request_text` | `TextField` | `blank=True` |
| `priority` | `CharField` | `max_length=24, default='normal', db_index=True` |
| `input_payload` | `JSONField` | `default=dict, blank=True` |
| `output_payload` | `JSONField` | `default=dict, blank=True` |
| `current_operation` | `CharField` | `max_length=255, blank=True` |
| `current_tool` | `CharField` | `max_length=120, blank=True` |
| `progress` | `PositiveSmallIntegerField` | `default=0` |
| `started_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `completed_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `cancellable` | `BooleanField` | `default=True` |
| `cancel_requested` | `BooleanField` | `default=False, db_index=True` |
| `error_message` | `TextField` | `blank=True` |
| `correlation_id` | `UUIDField` | `default=uuid.uuid4, db_index=True` |

### `AgentCommunication`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |
| `task` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='communications'` |
| `sender_agent` | `ForeignKey` | `on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_messages'` |
| `recipient_agent` | `ForeignKey` | `on_delete=models.SET_NULL, null=True, blank=True, related_name='received_messages'` |
| `message_type` | `CharField` | `max_length=64, default='handoff', db_index=True` |
| `correlation_id` | `UUIDField` | `default=uuid.uuid4, db_index=True` |
| `payload` | `JSONField` | `default=dict, blank=True` |
| `processed_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |

### `AgentGroup`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `AgentMembership`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `AgentPerformance`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

## `ai_engine`

### `AIModel`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `provider` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `model_identifier` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `max_context` | `BigIntegerField` | `default=0` |
| `max_output_tokens` | `BigIntegerField` | `default=0` |
| `supports_streaming` | `BooleanField` | `default=False` |
| `supports_tools` | `BooleanField` | `default=False` |
| `supports_images` | `BooleanField` | `default=False` |
| `supports_audio` | `BooleanField` | `default=False` |
| `cost_input` | `DecimalField` | `default=0` |
| `cost_output` | `DecimalField` | `default=0` |
| `enabled` | `BooleanField` | `default=False` |

### `AIProvider`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `api_endpoint` | `URLField` | `max_length=2048, blank=True` |
| `api_key_reference` | `UUIDField` | `null=True, blank=True, db_index=True` |
| `priority` | `BigIntegerField` | `default=0` |
| `enabled` | `BooleanField` | `default=False` |
| `rate_limit` | `BigIntegerField` | `default=0` |
| `timeout` | `BigIntegerField` | `default=0` |
| `retry_limit` | `BigIntegerField` | `default=0` |

### `PromptTemplate`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=255, blank=True, db_index=True` |
| `system_prompt` | `TextField` | `blank=True` |
| `template` | `TextField` | `blank=True` |
| `version` | `BigIntegerField` | `default=0` |
| `enabled` | `BooleanField` | `default=False` |

### `AIRequest`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `conversation` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `user` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='ai_engine_a_i_request_user'` |
| `provider` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `model` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `prompt_tokens` | `BigIntegerField` | `default=0` |
| `completion_tokens` | `BigIntegerField` | `default=0` |
| `latency` | `BigIntegerField` | `default=0` |
| `started_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `completed_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |

### `AIResponse`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `request` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `content` | `TextField` | `blank=True` |
| `finish_reason` | `TextField` | `blank=True` |
| `tool_calls` | `JSONField` | `default=dict, blank=True` |
| `cost` | `DecimalField` | `default=0` |

### `ToolInvocation`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `request` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `tool_name` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `arguments` | `JSONField` | `default=dict, blank=True` |
| `result` | `JSONField` | `default=dict, blank=True` |
| `started_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `finished_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |

### `ContextSnapshot`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

## `analytics`

### `AnalyticsEvent`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `MetricDefinition`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `MetricPoint`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `Report`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `DashboardSnapshot`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `UsageAggregate`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

## `api`

### `APIClient`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `APIKey`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `APIRequestLog`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `WebhookEndpoint`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `WebhookDelivery`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `IdempotencyRecord`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

## `authentication`

### `User`

Base: `AbstractUser`

| Field | Type | Important options |
|---|---|---|
| `id` | `UUIDField` | `default=uuid.uuid4` |
| `email` | `EmailField` | `unique=True` |
| `display_name` | `CharField` | `max_length=150, blank=True` |
| `phone` | `CharField` | `max_length=40, blank=True` |
| `country` | `CharField` | `max_length=2, blank=True` |
| `timezone` | `CharField` | `max_length=64, default='UTC'` |
| `language` | `CharField` | `max_length=12, default='en'` |
| `profile_picture` | `ImageField` | `blank=True` |
| `bio` | `TextField` | `blank=True` |
| `date_of_birth` | `DateField` | `null=True, blank=True` |
| `gender` | `CharField` | `max_length=32, blank=True` |
| `is_verified` | `BooleanField` | `default=False, db_index=True` |
| `is_deleted` | `BooleanField` | `default=False, db_index=True` |
| `created_at` | `DateTimeField` | `` |
| `updated_at` | `DateTimeField` | `` |
| `roles` | `ManyToManyField` | `related_name='users', blank=True` |

### `UserProfile`

Base: `UUIDModel`

| Field | Type | Important options |
|---|---|---|
| `user` | `OneToOneField` | `on_delete=models.CASCADE, related_name='profile'` |
| `theme` | `CharField` | `max_length=20, default='system'` |
| `accent_color` | `CharField` | `max_length=20, default='indigo'` |
| `font_size` | `CharField` | `max_length=20, default='medium'` |
| `dashboard_layout` | `JSONField` | `default=dict, blank=True` |
| `preferred_language` | `CharField` | `max_length=12, default='en'` |
| `preferred_ai_model` | `CharField` | `max_length=255, blank=True` |
| `notification_preferences` | `JSONField` | `default=dict, blank=True` |
| `timezone` | `CharField` | `max_length=64, default='UTC'` |

### `UserRole`

Base: `UUIDModel`

| Field | Type | Important options |
|---|---|---|
| `name` | `CharField` | `max_length=100, unique=True` |
| `description` | `TextField` | `blank=True` |
| `is_system` | `BooleanField` | `default=False` |

### `Permission`

Base: `UUIDModel`

| Field | Type | Important options |
|---|---|---|
| `name` | `CharField` | `max_length=150` |
| `codename` | `CharField` | `max_length=150, unique=True` |
| `description` | `TextField` | `blank=True` |

### `RolePermission`

Base: `UUIDModel`

| Field | Type | Important options |
|---|---|---|
| `role` | `ForeignKey` | `on_delete=models.CASCADE, related_name='permission_links'` |
| `permission` | `ForeignKey` | `on_delete=models.CASCADE, related_name='role_links'` |

### `UserDevice`

Base: `UUIDModel`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, related_name='devices'` |
| `device_name` | `CharField` | `max_length=255, blank=True` |
| `browser` | `CharField` | `max_length=255, blank=True` |
| `operating_system` | `CharField` | `max_length=255, blank=True` |
| `ip_address` | `GenericIPAddressField` | `null=True, blank=True` |
| `location` | `CharField` | `max_length=255, blank=True` |
| `trusted` | `BooleanField` | `default=False` |
| `last_login` | `DateTimeField` | `null=True, blank=True` |

### `LoginHistory`

Base: `UUIDModel`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, related_name='login_history'` |
| `ip_address` | `GenericIPAddressField` | `null=True, blank=True` |
| `browser` | `CharField` | `max_length=255, blank=True` |
| `device` | `CharField` | `max_length=255, blank=True` |
| `country` | `CharField` | `max_length=2, blank=True` |
| `city` | `CharField` | `max_length=120, blank=True` |
| `status` | `CharField` | `max_length=32, default='success'` |
| `login_time` | `DateTimeField` | `default=timezone.now` |
| `logout_time` | `DateTimeField` | `null=True, blank=True` |

### `EmailVerificationToken`

Base: `ExpiringToken`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, related_name='email_verification_tokens'` |

### `PasswordResetToken`

Base: `ExpiringToken`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, related_name='password_reset_tokens'` |

### `APIToken`

Base: `UUIDModel`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, related_name='api_tokens'` |
| `token_prefix` | `CharField` | `max_length=12, db_index=True` |
| `token_hash` | `CharField` | `max_length=64, unique=True` |
| `name` | `CharField` | `max_length=120` |
| `expires_at` | `DateTimeField` | `null=True, blank=True` |
| `last_used` | `DateTimeField` | `null=True, blank=True` |
| `revoked` | `BooleanField` | `default=False` |

### `UserSession`

Base: `UUIDModel`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, related_name='session_records'` |
| `session_key` | `CharField` | `max_length=64, unique=True` |
| `ip_address` | `GenericIPAddressField` | `null=True, blank=True` |
| `browser` | `CharField` | `max_length=255, blank=True` |
| `device` | `CharField` | `max_length=255, blank=True` |
| `expires_at` | `DateTimeField` | `db_index=True` |
| `active` | `BooleanField` | `default=True` |

## `calendar`

### `Calendar`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `Event`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `EventParticipant`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `response_status` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `RecurrenceRule`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `Reminder`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `AvailabilityRule`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `TimeBlock`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

## `chat`

### `Conversation`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='chat_conversation_user'` |
| `conversation_type` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `current_model` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `system_prompt` | `TextField` | `blank=True` |
| `temperature` | `DecimalField` | `default=0` |
| `max_tokens` | `BigIntegerField` | `default=0` |
| `is_pinned` | `BooleanField` | `default=False` |
| `is_archived` | `BooleanField` | `default=False` |
| `is_shared` | `BooleanField` | `default=False` |
| `share_token` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `last_message_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |

### `Message`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `conversation` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='message_conversation_items'` |
| `sender` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `role` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `content` | `TextField` | `blank=True` |
| `rendered_content` | `TextField` | `blank=True` |
| `token_count` | `BigIntegerField` | `default=0` |
| `message_type` | `TextField` | `blank=True` |
| `parent_message` | `TextField` | `blank=True` |
| `edited` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `edited_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |

### `MessageAttachment`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `message` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='message_attachment_message_items'` |
| `file_reference` | `UUIDField` | `null=True, blank=True, db_index=True` |
| `attachment_type` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `mime_type` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `file_size` | `BigIntegerField` | `default=0` |
| `checksum` | `TextField` | `blank=True` |
| `processing_status` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `MessageReaction`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `message` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='message_reaction_message_items'` |
| `user` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='chat_message_reaction_user'` |
| `reaction` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `ConversationFolder`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='chat_conversation_folder_user'` |
| `color` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `icon` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `ConversationTag`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `conversation` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='conversation_tag_conversation_items'` |
| `tag` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `SharedConversation`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `conversation` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='shared_conversation_conversation_items'` |
| `token` | `CharField` | `max_length=255, blank=True, db_index=True` |
| `expires_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `view_count` | `BigIntegerField` | `default=0` |

### `ChatSettings`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='chat_chat_settings_user'` |
| `default_model` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `default_temperature` | `DecimalField` | `default=0` |
| `streaming_enabled` | `BooleanField` | `default=False` |
| `markdown_enabled` | `BooleanField` | `default=False` |
| `code_highlighting` | `BooleanField` | `default=False` |
| `auto_title` | `BooleanField` | `default=False` |
| `auto_save` | `BooleanField` | `default=False` |
| `auto_memory` | `BooleanField` | `default=False` |

### `StreamingSession`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `conversation` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='streaming_session_conversation_items'` |
| `message` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='streaming_session_message_items'` |
| `started_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `finished_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `latency` | `BigIntegerField` | `default=0` |
| `tokens_generated` | `BigIntegerField` | `default=0` |

## `code_assistant`

### `CodeProject`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `SourceFile`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `CodeSymbol`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `supported_types` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `CodeReview`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `CodeIssue`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `Dependency`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `TestSuite`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

## `core`

### `SystemConfiguration`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `key` | `CharField` | `max_length=255, unique=True` |
| `value` | `JSONField` | `default=dict, blank=True` |
| `value_type` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `editable` | `BooleanField` | `default=False` |
| `category` | `CharField` | `max_length=255, blank=True, db_index=True` |

### `FeatureFlag`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `enabled` | `BooleanField` | `default=False` |
| `rollout_percentage` | `DecimalField` | `default=0` |
| `environment` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `SystemLog`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `level` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `module` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `message` | `TextField` | `blank=True` |
| `details` | `JSONField` | `default=dict, blank=True` |
| `user` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='core_system_log_user'` |
| `ip_address` | `GenericIPAddressField` | `null=True, blank=True` |

### `AuditLog`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `actor` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='core_audit_log_actor'` |
| `action` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `object_type` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `object_id` | `UUIDField` | `null=True, blank=True, db_index=True` |
| `old_data` | `JSONField` | `default=dict, blank=True` |
| `new_data` | `JSONField` | `default=dict, blank=True` |
| `timestamp` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `ScheduledTask`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `task_path` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `last_run` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `next_run` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `enabled` | `BooleanField` | `default=False` |
| `retry_count` | `BigIntegerField` | `default=0` |

### `UploadedFile`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `file_name` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `original_name` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `extension` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `mime_type` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `size` | `BigIntegerField` | `default=0` |
| `storage_path` | `URLField` | `max_length=2048, blank=True` |
| `checksum` | `TextField` | `blank=True` |
| `uploaded_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |

### `ApplicationRegistry`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `version` | `BigIntegerField` | `default=0` |
| `enabled` | `BooleanField` | `default=False` |
| `installed_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `last_updated` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `dependencies` | `JSONField` | `default=dict, blank=True` |

## `dashboard`

### `DashboardLayout`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='dashboard_dashboard_layout_user'` |
| `is_default` | `BooleanField` | `default=False` |
| `columns` | `BigIntegerField` | `default=0` |
| `theme` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `DashboardWidget`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `layout` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `widget_type` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `position_x` | `BigIntegerField` | `default=0` |
| `position_y` | `BigIntegerField` | `default=0` |
| `width` | `BigIntegerField` | `default=0` |
| `height` | `BigIntegerField` | `default=0` |
| `collapsed` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `visible` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `QuickAction`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='dashboard_quick_action_user'` |
| `icon` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `action` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `url` | `URLField` | `max_length=2048, blank=True` |
| `order` | `BigIntegerField` | `default=0` |
| `enabled` | `BooleanField` | `default=False` |

### `FavoriteItem`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='dashboard_favorite_item_user'` |
| `item_type` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `item_id` | `UUIDField` | `null=True, blank=True, db_index=True` |
| `icon` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `RecentActivity`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='dashboard_recent_activity_user'` |
| `activity_type` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `module` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `reference_id` | `UUIDField` | `null=True, blank=True, db_index=True` |

### `DashboardNotification`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='dashboard_dashboard_notification_user'` |
| `message` | `TextField` | `blank=True` |
| `priority` | `BigIntegerField` | `default=0` |
| `is_read` | `BooleanField` | `default=False` |
| `action_url` | `URLField` | `max_length=2048, blank=True` |
| `expires_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |

### `WidgetPreference`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `widget` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `key` | `CharField` | `max_length=255, blank=True, db_index=True` |
| `value` | `JSONField` | `default=dict, blank=True` |

## `documents`

### `Document`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `DocumentMetadata`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `DocumentContent`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `DocumentPage`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `DocumentVersion`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `DocumentTag`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ProcessingJob`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

## `email`

### `EmailAccount`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `EmailThread`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `EmailMessage`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `EmailAttachment`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `EmailLabel`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `EmailRule`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `EmailDraft`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

## `internet`

### `SearchProvider`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `provider_type` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `api_endpoint` | `URLField` | `max_length=2048, blank=True` |
| `api_key_reference` | `UUIDField` | `null=True, blank=True, db_index=True` |
| `priority` | `BigIntegerField` | `default=0` |
| `enabled` | `BooleanField` | `default=False` |
| `rate_limit` | `BigIntegerField` | `default=0` |
| `timeout` | `BigIntegerField` | `default=0` |

### `SearchQuery`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='internet_search_query_user'` |
| `query` | `TextField` | `blank=True` |
| `search_type` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `provider` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `language` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `region` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `safe_search` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `requested_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |

### `SearchResult`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `query` | `TextField` | `blank=True` |
| `url` | `URLField` | `max_length=2048, blank=True` |
| `snippet` | `TextField` | `blank=True` |
| `domain` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `rank` | `BigIntegerField` | `default=0` |
| `relevance_score` | `DecimalField` | `default=0` |
| `published_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `retrieved_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |

### `WebPage`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `url` | `URLField` | `max_length=2048, blank=True` |
| `status_code` | `TextField` | `blank=True` |
| `content_type` | `TextField` | `blank=True` |
| `language` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `metadata` | `JSONField` | `default=dict, blank=True` |
| `content_hash` | `TextField` | `blank=True` |
| `last_fetched` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `RSSFeed`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `url` | `URLField` | `max_length=2048, blank=True` |
| `category` | `CharField` | `max_length=255, blank=True, db_index=True` |
| `enabled` | `BooleanField` | `default=False` |
| `last_checked` | `DateTimeField` | `null=True, blank=True, db_index=True` |

### `WebsiteMonitor`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='internet_website_monitor_user'` |
| `url` | `URLField` | `max_length=2048, blank=True` |
| `check_interval` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `last_changed` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `notification_enabled` | `BooleanField` | `default=False` |

### `DomainReputation`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `domain` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `trust_score` | `DecimalField` | `default=0` |
| `category` | `CharField` | `max_length=255, blank=True, db_index=True` |
| `blacklisted` | `BooleanField` | `default=False` |
| `last_updated` | `DateTimeField` | `null=True, blank=True, db_index=True` |

### `Website`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `CrawledPage`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ApiConnection`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `Download`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `DomainPolicy`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `BrowserSession`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `engine` | `CharField` | `max_length=32, default='chrome', db_index=True` |
| `headless` | `BooleanField` | `default=False` |
| `current_url` | `URLField` | `max_length=4096, blank=True` |
| `current_title` | `CharField` | `max_length=512, blank=True` |
| `active_tab_handle` | `CharField` | `max_length=255, blank=True` |
| `started_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `ended_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `last_activity_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `BrowserObservation`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `session` | `ForeignKey` | `on_delete=models.CASCADE, related_name='observations'` |
| `sequence` | `PositiveIntegerField` | `default=0` |
| `url` | `URLField` | `max_length=4096, blank=True` |
| `page_title` | `CharField` | `max_length=512, blank=True` |
| `visible_text` | `TextField` | `blank=True` |
| `dom` | `JSONField` | `default=dict, blank=True` |
| `accessibility_tree` | `JSONField` | `default=dict, blank=True` |
| `viewport` | `JSONField` | `default=dict, blank=True` |
| `media` | `JSONField` | `default=list, blank=True` |
| `screenshot` | `FileField` | `blank=True` |
| `content_hash` | `CharField` | `max_length=64, blank=True, db_index=True` |
| `observed_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `BrowserAction`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `session` | `ForeignKey` | `on_delete=models.CASCADE, related_name='actions'` |
| `action_type` | `CharField` | `max_length=80, db_index=True` |
| `target` | `TextField` | `blank=True` |
| `arguments` | `JSONField` | `default=dict, blank=True` |
| `result` | `JSONField` | `default=dict, blank=True` |
| `pre_observation` | `ForeignKey` | `on_delete=models.SET_NULL, null=True, blank=True, related_name='actions_before'` |
| `post_observation` | `ForeignKey` | `on_delete=models.SET_NULL, null=True, blank=True, related_name='actions_after'` |
| `verified` | `BooleanField` | `default=False, db_index=True` |
| `started_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `completed_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `error_message` | `TextField` | `blank=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ComputerUseOperation`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `session` | `ForeignKey` | `on_delete=models.SET_NULL, null=True, blank=True, related_name='operations'` |
| `conversation` | `ForeignKey` | `on_delete=models.SET_NULL, null=True, blank=True, related_name='computer_use_operations'` |
| `request_text` | `TextField` | `` |
| `plan` | `JSONField` | `default=list, blank=True` |
| `result` | `JSONField` | `default=dict, blank=True` |
| `current_step` | `PositiveIntegerField` | `default=0` |
| `progress` | `PositiveSmallIntegerField` | `default=0` |
| `current_operation` | `CharField` | `max_length=255, blank=True` |
| `current_tool` | `CharField` | `max_length=120, blank=True` |
| `cancellable` | `BooleanField` | `default=True` |
| `cancel_requested` | `BooleanField` | `default=False, db_index=True` |
| `started_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `completed_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `error_message` | `TextField` | `blank=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `MediaUnderstanding`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `session` | `ForeignKey` | `on_delete=models.CASCADE, related_name='media_understandings'` |
| `operation` | `ForeignKey` | `on_delete=models.SET_NULL, null=True, blank=True, related_name='media_understandings'` |
| `source_url` | `URLField` | `max_length=4096, blank=True` |
| `media_metadata` | `JSONField` | `default=dict, blank=True` |
| `transcript` | `TextField` | `blank=True` |
| `visual_notes` | `TextField` | `blank=True` |
| `summary` | `TextField` | `blank=True` |
| `evidence` | `JSONField` | `default=list, blank=True` |
| `confidence` | `DecimalField` | `default=0` |
| `processed_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ComputerSession`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `environment` | `CharField` | `max_length=96, default='desktop.local', db_index=True` |
| `display_name` | `CharField` | `max_length=255, blank=True` |
| `started_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `ended_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `last_activity_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `active_window` | `JSONField` | `default=dict, blank=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ComputerObservation`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `session` | `ForeignKey` | `on_delete=models.CASCADE, related_name='observations'` |
| `sequence` | `PositiveIntegerField` | `default=0` |
| `screenshot` | `FileField` | `blank=True` |
| `ocr_text` | `TextField` | `blank=True` |
| `vision` | `JSONField` | `default=dict, blank=True` |
| `ui_tree` | `JSONField` | `default=dict, blank=True` |
| `window_info` | `JSONField` | `default=dict, blank=True` |
| `cursor` | `JSONField` | `default=dict, blank=True` |
| `viewport` | `JSONField` | `default=dict, blank=True` |
| `content_hash` | `CharField` | `max_length=64, blank=True, db_index=True` |
| `observed_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ComputerAction`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `session` | `ForeignKey` | `on_delete=models.CASCADE, related_name='actions'` |
| `action_type` | `CharField` | `max_length=80, db_index=True` |
| `target` | `JSONField` | `default=dict, blank=True` |
| `arguments` | `JSONField` | `default=dict, blank=True` |
| `result` | `JSONField` | `default=dict, blank=True` |
| `pre_observation` | `ForeignKey` | `on_delete=models.SET_NULL, null=True, blank=True, related_name='actions_before'` |
| `post_observation` | `ForeignKey` | `on_delete=models.SET_NULL, null=True, blank=True, related_name='actions_after'` |
| `verified` | `BooleanField` | `default=False, db_index=True` |
| `started_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `completed_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `error_message` | `TextField` | `blank=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

## `knowledge`

### `KnowledgeCollection`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `KnowledgeCategory`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `KnowledgeDocument`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `DocumentSection`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ContentBlock`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `supported_types` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `KnowledgeTag`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `KnowledgeVersion`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `KnowledgePermission`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `permissions` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `KnowledgeComment`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `KnowledgeAttachment`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

## `memory`

### `Memory`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='memory_memory_user'` |
| `content` | `TextField` | `blank=True` |
| `summary` | `TextField` | `blank=True` |
| `memory_type` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `category` | `CharField` | `max_length=255, blank=True, db_index=True` |
| `importance_score` | `DecimalField` | `default=0` |
| `confidence_score` | `DecimalField` | `default=0` |
| `access_count` | `BigIntegerField` | `default=0` |
| `last_accessed` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `created_from` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `source_type` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `MemoryCategory`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `color` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `icon` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `parent` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `MemoryTag`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `memory` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='memory_tag_memory_items'` |
| `tag` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `MemoryRelationship`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `source_memory` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `target_memory` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `relationship_type` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `strength` | `DecimalField` | `default=0` |

### `MemorySnapshot`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `memory` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='memory_snapshot_memory_items'` |
| `version` | `BigIntegerField` | `default=0` |
| `content` | `TextField` | `blank=True` |

### `MemoryAccessLog`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `memory` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='memory_access_log_memory_items'` |
| `user` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='memory_memory_access_log_user'` |
| `conversation` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `reason` | `TextField` | `blank=True` |
| `retrieval_score` | `DecimalField` | `default=0` |
| `accessed_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |

### `MemoryRule`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `rule_type` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `conditions` | `JSONField` | `default=dict, blank=True` |
| `actions` | `JSONField` | `default=dict, blank=True` |
| `enabled` | `BooleanField` | `default=False` |

### `WorkingMemory`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `conversation` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `context` | `JSONField` | `default=dict, blank=True` |
| `expires_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |

### `MemoryFeedback`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `memory` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='memory_feedback_memory_items'` |
| `user` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='memory_memory_feedback_user'` |
| `feedback` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `rating` | `DecimalField` | `default=0` |

## `notifications`

### `Notification`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `NotificationChannel`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `NotificationPreference`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `NotificationTemplate`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `DeliveryLog`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `NotificationDigest`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

## `planner`

### `Goal`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ExecutionPlan`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `PlanStep`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `StepDependency`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `dependency_types` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `PlanningSession`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `RiskAssessment`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

## `projects`

### `Workspace`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `Project`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ProjectMember`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `roles` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `ProjectLabel`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ProjectMilestone`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ProjectActivity`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ProjectSettings`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

## `settings`

### `UserSetting`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `SystemSetting`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `FeaturePreference`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `IntegrationSetting`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `SecretReference`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ConfigurationAudit`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

## `tasks`

### `Task`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `SubTask`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `TaskDependency`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `dependency_types` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `Reminder`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `RecurrenceRule`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `TaskAttachment`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `TimeEntry`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `TaskActivity`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

## `tool_manager`

### `Tool`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ToolCapability`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ToolExecution`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ToolPermission`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `permission_levels` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `ToolSecretReference`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ToolHealth`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

## `vector_database`

### `EmbeddingModel`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `provider` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `dimensions` | `BigIntegerField` | `default=0` |
| `version` | `BigIntegerField` | `default=0` |
| `max_tokens` | `BigIntegerField` | `default=0` |
| `enabled` | `BooleanField` | `default=False` |

### `VectorDocument`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `source_type` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `source_id` | `UUIDField` | `null=True, blank=True, db_index=True` |
| `namespace` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='vector_document_namespace_items'` |
| `language` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `VectorChunk`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `document` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `chunk_index` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `content` | `TextField` | `blank=True` |
| `token_count` | `BigIntegerField` | `default=0` |
| `embedding_model` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='vector_chunk_embedding_model_items'` |
| `embedding_version` | `BigIntegerField` | `default=0` |
| `metadata` | `JSONField` | `default=dict, blank=True` |

### `VectorIndex`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `provider` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `index_name` | `CharField` | `max_length=255, blank=True, db_index=False` |
| `dimensions` | `BigIntegerField` | `default=0` |
| `distance_metric` | `CharField` | `max_length=255, blank=True, db_index=False` |

### `SearchHistory`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `user` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='vector_database_search_history_user'` |
| `query` | `TextField` | `blank=True` |
| `namespace` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='search_history_namespace_items'` |
| `results` | `JSONField` | `default=dict, blank=True` |
| `latency` | `BigIntegerField` | `default=0` |

### `Namespace`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

## `voice`

### `VoiceProfile`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, default='default', db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |
| `language` | `CharField` | `max_length=32, default='en-US'` |
| `speech_to_text_provider` | `CharField` | `max_length=64, default='browser'` |
| `text_to_speech_provider` | `CharField` | `max_length=64, default='browser'` |
| `voice_name` | `CharField` | `max_length=160, blank=True` |
| `speaking_rate` | `DecimalField` | `default=1` |
| `pitch` | `DecimalField` | `default=1` |
| `volume` | `DecimalField` | `default=1` |
| `auto_speak` | `BooleanField` | `default=True` |
| `continuous_listening` | `BooleanField` | `default=True` |
| `barge_in_enabled` | `BooleanField` | `default=True` |
| `save_audio` | `BooleanField` | `default=False` |
| `memory_requires_approval` | `BooleanField` | `default=True` |
| `speaker_identification_enabled` | `BooleanField` | `default=False` |
| `reject_unrecognized_speakers` | `BooleanField` | `default=True` |
| `voice_history_enabled` | `BooleanField` | `default=True` |
| `transcript_retention_days` | `PositiveSmallIntegerField` | `default=30` |
| `active_session_minutes` | `PositiveSmallIntegerField` | `default=60` |
| `is_default` | `BooleanField` | `default=True, db_index=True` |

### `VoiceSession`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, default='conversation', db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |
| `conversation` | `ForeignKey` | `on_delete=models.SET_NULL, null=True, blank=True, related_name='voice_sessions'` |
| `profile` | `ForeignKey` | `on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions'` |
| `state` | `CharField` | `max_length=32, default=State.STARTING, db_index=True` |
| `mode` | `CharField` | `max_length=24, default=Mode.WAKE_WORD, db_index=True` |
| `active_started_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `active_expires_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `wake_word` | `CharField` | `max_length=80, default='Echo'` |
| `speaker_state` | `CharField` | `max_length=32, default='not_enrolled', db_index=True` |
| `client_session_id` | `CharField` | `max_length=120, blank=True, db_index=True` |
| `input_mode` | `CharField` | `max_length=32, default='voice'` |
| `language` | `CharField` | `max_length=32, default='en-US'` |
| `stt_provider` | `CharField` | `max_length=64, default='browser'` |
| `tts_provider` | `CharField` | `max_length=64, default='browser'` |
| `started_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `ended_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `last_activity_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |
| `turn_count` | `PositiveIntegerField` | `default=0` |
| `last_error_code` | `CharField` | `max_length=80, blank=True` |
| `last_error_message` | `TextField` | `blank=True` |

### `AudioAsset`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, default='speech', db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |
| `session` | `ForeignKey` | `on_delete=models.CASCADE, null=True, blank=True, related_name='audio_assets'` |
| `file` | `FileField` | `blank=True` |
| `direction` | `CharField` | `max_length=16, default=Direction.INPUT` |
| `provider` | `CharField` | `max_length=64, blank=True` |
| `mime_type` | `CharField` | `max_length=120, blank=True` |
| `format_name` | `CharField` | `max_length=24, blank=True` |
| `byte_size` | `PositiveBigIntegerField` | `default=0` |
| `duration_ms` | `PositiveIntegerField` | `default=0` |
| `checksum` | `CharField` | `max_length=64, blank=True, db_index=True` |
| `expires_at` | `DateTimeField` | `null=True, blank=True, db_index=True` |

### `SpeechTranscript`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, default='utterance', db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |
| `session` | `ForeignKey` | `on_delete=models.CASCADE, related_name='transcripts', null=True, blank=True` |
| `conversation` | `ForeignKey` | `on_delete=models.SET_NULL, related_name='voice_transcripts', null=True, blank=True` |
| `message` | `ForeignKey` | `on_delete=models.SET_NULL, related_name='voice_transcripts', null=True, blank=True` |
| `audio_asset` | `ForeignKey` | `on_delete=models.SET_NULL, related_name='transcripts', null=True, blank=True` |
| `sequence` | `PositiveIntegerField` | `default=0` |
| `text` | `TextField` | `` |
| `language` | `CharField` | `max_length=32, default='en-US'` |
| `provider` | `CharField` | `max_length=64, default='browser'` |
| `confidence` | `DecimalField` | `default=0` |
| `is_final` | `BooleanField` | `default=True` |
| `intent` | `CharField` | `max_length=80, blank=True, db_index=True` |
| `command_route` | `CharField` | `max_length=80, blank=True, db_index=True` |
| `command_result` | `JSONField` | `default=dict, blank=True` |
| `memory_status` | `CharField` | `max_length=24, default=MemoryStatus.NOT_CANDIDATE, db_index=True` |
| `started_at` | `DateTimeField` | `null=True, blank=True` |
| `completed_at` | `DateTimeField` | `null=True, blank=True` |

### `SpeechSynthesis`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, default='response', db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |
| `session` | `ForeignKey` | `on_delete=models.CASCADE, related_name='syntheses', null=True, blank=True` |
| `message` | `ForeignKey` | `on_delete=models.SET_NULL, related_name='voice_syntheses', null=True, blank=True` |
| `audio_asset` | `ForeignKey` | `on_delete=models.SET_NULL, related_name='syntheses', null=True, blank=True` |
| `text` | `TextField` | `` |
| `provider` | `CharField` | `max_length=64, default='browser'` |
| `voice_name` | `CharField` | `max_length=160, blank=True` |
| `language` | `CharField` | `max_length=32, default='en-US'` |
| `format_name` | `CharField` | `max_length=24, default='mp3'` |
| `duration_ms` | `PositiveIntegerField` | `default=0` |
| `started_at` | `DateTimeField` | `null=True, blank=True` |
| `completed_at` | `DateTimeField` | `null=True, blank=True` |
| `error_message` | `TextField` | `blank=True` |

### `WakeWordConfiguration`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, default='wake_word', db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |
| `phrase` | `CharField` | `max_length=80, default='Echo'` |
| `enabled` | `BooleanField` | `default=True` |
| `sensitivity` | `DecimalField` | `default=0.7` |
| `require_foreground` | `BooleanField` | `default=True` |

### `VoiceEvent`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `session` | `ForeignKey` | `on_delete=models.CASCADE, related_name='events'` |
| `event_type` | `CharField` | `max_length=64, db_index=True` |
| `from_state` | `CharField` | `max_length=32, blank=True` |
| `to_state` | `CharField` | `max_length=32, blank=True` |
| `detail` | `TextField` | `blank=True` |
| `payload` | `JSONField` | `default=dict, blank=True` |

### `SpeakerProfile`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, default='speaker', db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |
| `enabled` | `BooleanField` | `default=True, db_index=True` |
| `enrolled` | `BooleanField` | `default=False, db_index=True` |
| `embedding` | `JSONField` | `default=list, blank=True` |
| `sample_count` | `PositiveSmallIntegerField` | `default=0` |
| `threshold` | `DecimalField` | `default=0.82` |
| `enrolled_at` | `DateTimeField` | `null=True, blank=True` |
| `last_verified_at` | `DateTimeField` | `null=True, blank=True` |

### `SpeakerEnrollmentSample`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, default='speaker_sample', db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |
| `profile` | `ForeignKey` | `on_delete=models.CASCADE, related_name='samples'` |
| `embedding` | `JSONField` | `default=list, blank=True` |
| `quality_score` | `DecimalField` | `default=0` |
| `duration_ms` | `PositiveIntegerField` | `default=0` |

### `SpeakerVerificationEvent`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, default='speaker_verification', db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |
| `profile` | `ForeignKey` | `on_delete=models.CASCADE, related_name='verification_events'` |
| `session` | `ForeignKey` | `on_delete=models.SET_NULL, null=True, blank=True, related_name='speaker_events'` |
| `transcript` | `ForeignKey` | `on_delete=models.SET_NULL, null=True, blank=True, related_name='speaker_events'` |
| `decision` | `CharField` | `max_length=24, default='unknown', db_index=True` |
| `score` | `DecimalField` | `default=0` |
| `threshold` | `DecimalField` | `default=0.82` |

## `workflow_engine`

### `Workflow`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `WorkflowExecution`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `WorkflowStep`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `StepDependency`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `ExecutionEvent`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `Checkpoint`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

### `RetryHistory`

Base: `DomainModel`

| Field | Type | Important options |
|---|---|---|
| `category` | `CharField` | `max_length=100, blank=True, db_index=True` |
| `configuration` | `JSONField` | `default=dict, blank=True` |

