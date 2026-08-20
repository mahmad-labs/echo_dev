from django.apps import apps


def platform_context(request):
    return {'echo_modules': [config.verbose_name for config in apps.get_app_configs() if config.name.startswith('echo.apps.')], 'platform_name': 'Echo'}
