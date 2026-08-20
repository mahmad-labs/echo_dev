from echo.common.services import DomainService

from .models import CodeProject, SourceFile, CodeReview, TestSuite, CodeSymbol

class CodeService(DomainService):
    model = CodeProject

class AnalysisService(DomainService):
    model = SourceFile

class ReviewService(DomainService):
    model = CodeReview

class RepositoryService(DomainService):
    model = CodeProject

class TestingService(DomainService):
    model = TestSuite

class DocumentationService(DomainService):
    model = SourceFile

class IndexingService(DomainService):
    model = CodeSymbol
