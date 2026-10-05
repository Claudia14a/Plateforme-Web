from django.urls import include, path
from rest_framework.routers import DefaultRouter
from candidatures.views import CandidaturesRecuesViewSet, MesCandidaturesViewSet

router = DefaultRouter()
router.register(r'mes-candidatures', MesCandidaturesViewSet, basename='mes-candidatures')
router.register(r'recues', CandidaturesRecuesViewSet, basename='candidatures-recues')

urlpatterns = [
    path('', include(router.urls)),
]
