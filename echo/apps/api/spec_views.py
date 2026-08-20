from __future__ import annotations

import re
import uuid

from django.apps import apps
from django.db import transaction
from django.db.models import Q
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from echo.common.serializers import DynamicModelSerializer
from echo.spec_catalog import SPEC_ENDPOINTS

from .operations import dispatch_operation


STATUS_ACTIONS = {
    'activate': 'active',
    'deactivate': 'inactive',
    'archive': 'archived',
    'restore': 'active',
    'cancel': 'cancelled',
    'pause': 'paused',
    'resume': 'running',
    'complete': 'completed',
    'retry': 'queued',
    'execute': 'running',
    'run': 'running',
    'sync': 'synchronizing',
    'process': 'processing',
    'index': 'indexing',
    'send': 'sent',
}


def normalize(value: str) -> str:
    return re.sub(r'[^a-z0-9]', '', value.lower())


APP_ROOTS = {
    'core': 'core',
    'dashboard': 'dashboard',
    'chat': 'chat',
    'ai': 'ai_engine',
    'memory': 'memory',
    'vector': 'vector_database',
    'knowledge': 'knowledge',
    'documents': 'documents',
    'internet': 'internet',
    'code': 'code_assistant',
    'planner': 'planner',
    'agents': 'agent_manager',
    'workflows': 'workflow_engine',
    'tools': 'tool_manager',
    'tasks': 'tasks',
    'calendar': 'calendar',
    'email': 'email',
    'notifications': 'notifications',
    'projects': 'projects',
    'analytics': 'analytics',
    'settings': 'settings',
    'voice': 'voice',
}

RESOURCE_MODELS = {
    'core': {'config': 'SystemConfiguration', 'features': 'FeatureFlag', 'logs': 'SystemLog', 'audit': 'AuditLog', 'files': 'UploadedFile'},
    'dashboard': {'layout': 'DashboardLayout', 'widgets': 'DashboardWidget', 'actions': 'QuickAction', 'notifications': 'DashboardNotification'},
    'chat': {'conversations': 'Conversation', 'messages': 'Message', 'attachments': 'MessageAttachment'},
    'ai_engine': {'models': 'AIModel', 'providers': 'AIProvider', 'history': 'AIRequest', 'prompts': 'PromptTemplate', 'request': 'AIRequest'},
    'memory': {'memory': 'Memory', 'categories': 'MemoryCategory', 'relationships': 'MemoryRelationship', 'feedback': 'MemoryFeedback'},
    'vector_database': {'index': 'VectorIndex', 'documents': 'VectorDocument', 'namespaces': 'Namespace'},
    'knowledge': {'collections': 'KnowledgeCollection', 'categories': 'KnowledgeCategory', 'documents': 'KnowledgeDocument', 'versions': 'KnowledgeVersion'},
    'documents': {'documents': 'Document', 'jobs': 'ProcessingJob'},
    'internet': {'rss': 'RSSFeed', 'monitors': 'WebsiteMonitor', 'history': 'SearchQuery', 'downloads': 'Download', 'monitoring': 'WebsiteMonitor'},
    'code_assistant': {'projects': 'CodeProject', 'issues': 'CodeIssue', 'dependencies': 'Dependency'},
    'planner': {'goals': 'Goal', 'plans': 'ExecutionPlan', 'steps': 'PlanStep'},
    'agent_manager': {'agents': 'Agent', 'tasks': 'AgentTask', 'capabilities': 'AgentCapability', 'groups': 'AgentGroup', 'performance': 'AgentPerformance'},
    'workflow_engine': {'workflows': 'Workflow', 'executions': 'WorkflowExecution', 'steps': 'WorkflowStep', 'checkpoints': 'Checkpoint'},
    'tool_manager': {'tools': 'Tool', 'registry': 'Tool', 'health': 'ToolHealth', 'analytics': 'ToolExecution'},
    'tasks': {'tasks': 'Task', 'subtasks': 'SubTask', 'reminders': 'Reminder'},
    'calendar': {'calendar': 'Calendar', 'events': 'Event', 'availability': 'AvailabilityRule', 'reminders': 'Reminder'},
    'email': {'accounts': 'EmailAccount', 'messages': 'EmailMessage', 'drafts': 'EmailDraft'},
    'notifications': {'notifications': 'Notification', 'preferences': 'NotificationPreference', 'templates': 'NotificationTemplate', 'digests': 'NotificationDigest', 'delivery': 'DeliveryLog'},
    'projects': {'projects': 'Project', 'workspaces': 'Workspace', 'members': 'ProjectMember', 'milestones': 'ProjectMilestone'},
}


def model_for_path(path: str):
    raw_tokens = [part.lower() for part in path.split('/') if part]
    normalized_tokens = [normalize(part) for part in raw_tokens if not path_uuid(part)]
    if not normalized_tokens:
        return None
    app_label = APP_ROOTS.get(normalized_tokens[0])
    candidates = list(apps.get_app_config(app_label).get_models()) if app_label else list(apps.get_models())

    resource_map = RESOURCE_MODELS.get(app_label or '', {})
    for token in reversed(normalized_tokens[1:] or normalized_tokens):
        model_name = resource_map.get(token)
        if model_name:
            return apps.get_model(app_label, model_name)

    scored = []
    for model in candidates:
        model_name = normalize(model._meta.model_name)
        verbose_name = normalize(str(model._meta.verbose_name))
        aliases = {model_name, f'{model_name}s', verbose_name, f'{verbose_name}s'}
        best = 0
        for token in normalized_tokens:
            for alias in aliases:
                if token == alias:
                    score = 10_000 + len(alias)
                elif token in alias or alias in token:
                    score = min(len(token), len(alias)) * 10 - abs(len(token) - len(alias))
                else:
                    score = 0
                best = max(best, score)
        if best:
            scored.append((best, -len(model_name), model._meta.label_lower, model))
    return max(scored, key=lambda item: (item[0], item[1], item[2]))[3] if scored else None


def path_uuid(path: str) -> uuid.UUID | None:
    for part in path.split('/'):
        try:
            return uuid.UUID(part)
        except (ValueError, AttributeError):
            continue
    return None


def requested_action(path: str) -> str | None:
    parts = [normalize(part) for part in path.split('/') if part]
    return next((part for part in reversed(parts) if part in STATUS_ACTIONS), None)


class EndpointCatalogView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        return Response({'count': len(SPEC_ENDPOINTS), 'endpoints': SPEC_ENDPOINTS})


class SpecEndpointView(APIView):
    PUBLIC_GET_PATHS = {'core/health', 'core/status', 'core/version'}

    def dispatch(self, request, *args, **kwargs):
        self.resource_path = kwargs.get('resource_path', '').strip('/')
        return super().dispatch(request, *args, **kwargs)

    def get_permissions(self):
        is_public_share = self.request.method == 'GET' and self.resource_path.startswith('chat/share/')
        is_public_status = self.request.method == 'GET' and self.resource_path in self.PUBLIC_GET_PATHS
        if is_public_share or is_public_status:
            return [permissions.AllowAny()]
        return super().get_permissions()

    def _queryset(self, request, model):
        queryset = model.objects.all()
        names = {field.name for field in model._meta.fields}
        if request.user.is_staff:
            return queryset
        if 'owner' in names:
            return queryset.filter(owner=request.user)
        if 'user' in names:
            return queryset.filter(user=request.user)
        if 'actor' in names:
            return queryset.filter(actor=request.user)
        return queryset.none()

    def _serializer(self, model, *args, **kwargs):
        serializer_class = type(
            f'{model.__name__}CompatibilitySerializer',
            (DynamicModelSerializer,),
            {
                'Meta': type(
                    'Meta',
                    (),
                    {
                        'model': model,
                        'fields': '__all__',
                        'read_only_fields': ('id', 'created_at', 'updated_at', 'owner', 'user', 'actor'),
                    },
                )
            },
        )
        return serializer_class(*args, **kwargs)

    def _analytics(self, request):
        totals = {}
        for app_config in apps.get_app_configs():
            if not app_config.name.startswith('echo.apps.'):
                continue
            totals[app_config.label] = sum(
                self._queryset(request, model).count() for model in app_config.get_models()
            )
        return Response({'totals': totals, 'grand_total': sum(totals.values())})

    def _record_operation(self, request, resource_path: str):
        request_log_model = apps.get_model('api', 'APIRequestLog')
        operation = request_log_model.objects.create(
            owner=request.user,
            name=resource_path,
            title=f'{request.method} /api/{resource_path}/',
            status='accepted',
            data={
                'method': request.method,
                'path': resource_path,
                'payload': request.data,
                'correlation_id': getattr(request, 'correlation_id', None),
            },
        )
        return Response(
            {
                'operation_id': operation.pk,
                'status': operation.status,
                'correlation_id': getattr(request, 'correlation_id', None),
            },
            status=status.HTTP_202_ACCEPTED,
        )

    def get(self, request, resource_path=''):
        operational_response = dispatch_operation(request, resource_path)
        if operational_response is not None:
            return operational_response
        if 'analytics' in normalize(resource_path) or 'overview' in normalize(resource_path):
            return self._analytics(request)

        model = model_for_path(resource_path)
        if not model:
            matching = [
                endpoint
                for endpoint in SPEC_ENDPOINTS
                if endpoint['path'].strip('/').replace('<id>', '') in resource_path
            ]
            return Response(
                {
                    'path': f'/api/{resource_path}/',
                    'registered': bool(matching),
                    'allowed_methods': sorted({item['method'] for item in matching}),
                }
            )

        queryset = self._queryset(request, model)
        query = request.query_params.get('q') or request.query_params.get('search')
        if query:
            names = {field.name for field in model._meta.fields}
            filters = Q()
            for name in ('name', 'title', 'description', 'content', 'summary'):
                if name in names:
                    filters |= Q(**{f'{name}__icontains': query})
            if filters:
                queryset = queryset.filter(filters)

        identifier = path_uuid(resource_path)
        if identifier:
            instance = queryset.filter(pk=identifier).first()
            if not instance:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(
                self._serializer(model, instance, context={'request': request}).data
            )

        serializer = self._serializer(
            model,
            queryset[:100],
            many=True,
            context={'request': request},
        )
        return Response(serializer.data)

    @transaction.atomic
    def post(self, request, resource_path=''):
        operational_response = dispatch_operation(request, resource_path)
        if operational_response is not None:
            return operational_response
        model = model_for_path(resource_path)
        identifier = path_uuid(resource_path)
        action = requested_action(resource_path)

        if model and identifier and action:
            instance = self._queryset(request, model).filter(pk=identifier).first()
            if not instance:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
            if hasattr(instance, 'status'):
                instance.status = STATUS_ACTIONS[action]
            if hasattr(instance, 'data'):
                instance.data = {
                    **(instance.data or {}),
                    'last_action': action,
                    'action_payload': request.data,
                    'correlation_id': getattr(request, 'correlation_id', None),
                }
            instance.full_clean()
            instance.save()
            return Response(
                self._serializer(model, instance, context={'request': request}).data
            )

        if not model:
            return self._record_operation(request, resource_path)

        payload = request.data.copy()
        names = {field.name for field in model._meta.fields}
        if 'owner' in names:
            payload['owner'] = str(request.user.pk)
        elif 'user' in names:
            payload['user'] = str(request.user.pk)
        elif 'actor' in names:
            payload['actor'] = str(request.user.pk)
        serializer = self._serializer(model, data=payload, context={'request': request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            self._serializer(model, instance, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, resource_path=''):
        operational_response = dispatch_operation(request, resource_path)
        if operational_response is not None:
            return operational_response
        return self._update(request, partial=False)

    def patch(self, request, resource_path=''):
        return self._update(request, partial=True)

    def _update(self, request, partial: bool):
        model = model_for_path(self.resource_path)
        identifier = path_uuid(self.resource_path)
        if not model or not identifier:
            return Response(
                {'detail': 'A resource identifier is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = self._queryset(request, model).filter(pk=identifier).first()
        if not instance:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self._serializer(
            model,
            instance,
            data=request.data,
            partial=partial,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, resource_path=''):
        model = model_for_path(resource_path)
        identifier = path_uuid(resource_path)
        if not model or not identifier:
            return Response(
                {'detail': 'A resource identifier is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = self._queryset(request, model).filter(pk=identifier).first()
        if not instance:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
