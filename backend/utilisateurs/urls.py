from django.urls import include, path
from rest_framework.routers import DefaultRouter
from utilisateurs.views import (
    EtudiantPublicViewSet,
    ProfilEntrepriseViewSet,
    ProfilEtudiantViewSet,
    RegisterView,
)

router = DefaultRouter()
router.register(r'profils-etudiants', ProfilEtudiantViewSet, basename='profil-etudiant')
router.register(r'profils-entreprises', ProfilEntrepriseViewSet, basename='profil-entreprise')
router.register(r'etudiants', EtudiantPublicViewSet, basename='etudiant-public')  # annuaire public

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('', include(router.urls)),
]
