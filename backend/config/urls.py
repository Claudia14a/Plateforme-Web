from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/login/', TokenObtainPairView.as_view()),
    path('api/auth/refresh/', TokenRefreshView.as_view()),
    path('api/utilisateurs/', include('utilisateurs.urls')),
    path('api/offres/', include('offres.urls')),
    path('api/candidatures/', include('candidatures.urls')),
    path('api/conventions/', include('conventions.urls')),
    path('api/notifications/', include('notifications.urls')),
]