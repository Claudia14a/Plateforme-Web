from django.urls import include, path
from rest_framework.routers import DefaultRouter
from offres.views import OffreStageViewSet

router = DefaultRouter()
router.register(r'offres', OffreStageViewSet, basename='offre-stage')

urlpatterns = [
    path('', include(router.urls)),
]
