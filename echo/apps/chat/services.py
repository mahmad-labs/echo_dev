from echo.common.services import DomainService

from .models import Conversation, Message, StreamingSession, MessageAttachment, SharedConversation

class ChatService(DomainService):
    model = Conversation

class ConversationService(DomainService):
    model = Conversation

class MessageService(DomainService):
    model = Message

class StreamingService(DomainService):
    model = StreamingSession

class ContextService(DomainService):
    model = Conversation

class AttachmentService(DomainService):
    model = MessageAttachment

class ExportService(DomainService):
    model = SharedConversation

class SearchService(DomainService):
    model = Message
