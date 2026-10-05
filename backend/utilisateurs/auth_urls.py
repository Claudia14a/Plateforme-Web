from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from utilisateurs.views import (
    LoginView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ResendVerificationView,
    VerifyEmailView,
)

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('me/', MeView.as_view(), name='me'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('resend-verification/', ResendVerificationView.as_view(), name='resend-verification'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
]
