from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone


def health(request):
    return JsonResponse({'status': 'ok', 'service': 'echo', 'timestamp': timezone.now().isoformat()})


def readiness(request):
    checks = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            checks['database'] = cursor.fetchone()[0] == 1
    except Exception as exc:
        checks['database'] = False
        checks['database_error'] = exc.__class__.__name__
    try:
        cache.set('echo-readiness', 'ok', 10)
        checks['cache'] = cache.get('echo-readiness') == 'ok'
    except Exception as exc:
        checks['cache'] = False
        checks['cache_error'] = exc.__class__.__name__
    code = 200 if all(value is True for key, value in checks.items() if not key.endswith('_error')) else 503
    return JsonResponse({'status': 'ready' if code == 200 else 'degraded', 'checks': checks}, status=code)


def metrics(request):
    from django.apps import apps
    values = {'models': sum(1 for _ in apps.get_models()), 'applications': sum(1 for app in apps.get_app_configs() if app.name.startswith('echo.apps.'))}
    return JsonResponse(values)
