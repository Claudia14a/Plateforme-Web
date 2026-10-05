from django.urls import include, path
from rest_framework.routers import SimpleRouter
from conventions.views import ConventionViewSet

router = SimpleRouter()
router.register(r'', ConventionViewSet, basename='convention')

urlpatterns = [
    path('', include(router.urls)),
]
