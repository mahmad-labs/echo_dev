from django.apps import apps
from django.contrib import admin

for model in apps.get_app_config(__package__.split('.')[-1]).get_models():
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
