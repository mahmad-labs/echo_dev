from django.apps import apps
from rest_framework.routers import DefaultRouter

from .serializers import DynamicModelSerializer
from .viewsets import SecuredModelViewSet


FILTERABLE_TYPES = {
    'BooleanField', 'CharField', 'DateField', 'DateTimeField', 'DecimalField',
    'EmailField', 'FloatField', 'ForeignKey', 'IntegerField', 'PositiveIntegerField',
    'PositiveSmallIntegerField', 'SlugField', 'SmallIntegerField', 'UUIDField',
}


def build_app_router(app_label: str) -> DefaultRouter:
    router = DefaultRouter()
    app_config = apps.get_app_config(app_label)
    for model in sorted(app_config.get_models(), key=lambda value: value.__name__):
        serializer = type(
            f'{model.__name__}Serializer',
            (DynamicModelSerializer,),
            {'Meta': type('Meta', (), {
                'model': model,
                'fields': '__all__',
                'read_only_fields': ('id', 'created_at', 'updated_at', 'owner', 'user', 'actor'),
            })},
        )
        concrete_fields = tuple(model._meta.fields)
        viewset = type(
            f'{model.__name__}ViewSet',
            (SecuredModelViewSet,),
            {
                'queryset': model.objects.all(),
                'serializer_class': serializer,
                'search_fields': tuple(
                    field.name for field in concrete_fields
                    if field.get_internal_type() in {'CharField', 'TextField', 'EmailField'}
                ),
                'filterset_fields': tuple(
                    field.name for field in concrete_fields
                    if field.get_internal_type() in FILTERABLE_TYPES
                ),
            },
        )
        basename = model._meta.model_name.replace('_', '-')
        router.register(basename, viewset, basename=f'{app_label}-{basename}')
    return router
