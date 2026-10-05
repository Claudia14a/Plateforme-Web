from django.urls import include, path
from rest_framework.routers import DefaultRouter
from utilisateurs.views import (
    ProfilEntrepriseViewSet,
    ProfilEtudiantViewSet,
    RegisterView,
)

router = DefaultRouter()
router.register(r'profils-etudiants', ProfilEtudiantViewSet, basename='profil-etudiant')
router.register(r'profils-entreprises', ProfilEntrepriseViewSet, basename='profil-entreprise')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('', include(router.urls)),
]
