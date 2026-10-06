from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('utilisateurs.auth_urls')),
    path('api/utilisateurs/', include('utilisateurs.urls')),
    path('api/offres/', include('offres.urls')),
    path('api/candidatures/', include('candidatures.urls')),
    path('api/conventions/', include('conventions.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/admin/', include('administration.urls')),  # tableau de bord, utilisateurs, journal, rapports
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  # logos en développement (DEBUG)
