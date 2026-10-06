from django.urls import include, path
from rest_framework.routers import DefaultRouter
from administration.views import (
    JournalAuditViewSet,
    RapportCandidaturesCSVView,
    StatistiquesView,
    TableauDeBordView,
    UtilisateurAdminViewSet,
)

router = DefaultRouter()
router.register(r'utilisateurs', UtilisateurAdminViewSet, basename='admin-utilisateurs')
router.register(r'journal', JournalAuditViewSet, basename='admin-journal')

urlpatterns = [
    path('tableau-de-bord/', TableauDeBordView.as_view(), name='admin-tableau-de-bord'),
    path('statistiques/', StatistiquesView.as_view(), name='admin-statistiques'),
    path('rapports/candidatures.csv', RapportCandidaturesCSVView.as_view(), name='admin-rapport-candidatures'),
    path('', include(router.urls)),
]
