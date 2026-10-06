from django.apps import AppConfig


class CandidaturesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'candidatures'

    def ready(self):
        from candidatures import signals  # noqa: F401  (branche les réactions aux changements de statut)
