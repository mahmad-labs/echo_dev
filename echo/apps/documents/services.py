from echo.common.services import DomainService

from .models import Document, DocumentContent, DocumentMetadata, ProcessingJob, DocumentVersion

class UploadService(DomainService):
    model = Document

class ExtractionService(DomainService):
    model = DocumentContent

class MetadataService(DomainService):
    model = DocumentMetadata

class ProcessingService(DomainService):
    model = ProcessingJob

class ConversionService(DomainService):
    model = DocumentVersion

class DuplicateService(DomainService):
    model = Document

class IndexingService(DomainService):
    model = DocumentContent
