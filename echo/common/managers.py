from django.db import models


class ActiveQuerySet(models.QuerySet):
    def active(self):
        if any(field.name == 'is_active' for field in self.model._meta.fields):
            return self.filter(is_active=True)
        if any(field.name == 'status' for field in self.model._meta.fields):
            return self.exclude(status__in=['deleted', 'archived', 'disabled'])
        return self
