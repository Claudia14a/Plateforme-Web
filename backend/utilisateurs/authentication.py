from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class JWTAuthenticationOptionnelle(JWTAuthentication):
  """Authentification JWT « tolérante », pour les pages publiques.

  - sans token            -> visiteur anonyme
  - token valide          -> utilisateur connecté (il voit ses propres offres en plus)
  - token expiré/invalide -> visiteur anonyme (au lieu d'une erreur 401 qui casserait
                             la consultation publique des offres)
  À n'utiliser que sur des routes en lecture seule dont la permission est AllowAny.
  """

  def authenticate(self, request):
    try:
      return super().authenticate(request)
    except (InvalidToken, AuthenticationFailed):
      return None
