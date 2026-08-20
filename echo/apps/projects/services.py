from echo.common.services import DomainService

from .models import Project, Workspace, ProjectMember, ProjectActivity

class ProjectService(DomainService):
    model = Project

class WorkspaceService(DomainService):
    model = Workspace

class MembershipService(DomainService):
    model = ProjectMember

class SharingService(DomainService):
    model = ProjectMember

class ArchiveService(DomainService):
    model = Project

class SearchService(DomainService):
    model = Project

class BackupService(DomainService):
    model = Project

class AnalyticsService(DomainService):
    model = ProjectActivity
