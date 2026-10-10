from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from utilisateurs.emails import envoyer_email_reinitialisation, envoyer_email_verification
from utilisateurs.two_factor import (
    EmailIndisponible,
    REGISTER,
    creer_mfa_token,
    deux_facteurs_actif,
    envoyer_code,
    masquer_email,
    validite_minutes,
)
from utilisateurs.authentication import JWTAuthenticationOptionnelle
from utilisateurs.filters import EtudiantPublicFilter, ProfilEntrepriseFilter
from utilisateurs.models import ProfilEntreprise, ProfilEtudiant, User
from utilisateurs.permissions import IsEntrepriseOrAdmin, IsEtudiant, IsEtudiantOrAdmin
from utilisateurs.throttles import ProfilsPublicsThrottle
from utilisateurs.serializers import (
    EmailSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    ProfilEntreprisePublicSerializer,
    ProfilEntrepriseSerializer,
    ProfilEtudiantPublicSerializer,
    ProfilEtudiantSerializer,
    RegisterSerializer,
    Renvoyer2FASerializer,
    UserSerializer,
    Verify2FASerializer,
    VerifyEmailSerializer,
)


class AuthRateThrottle(AnonRateThrottle):
  """Anti-abus (connexion, inscription, vérification) : 60 appels/min par adresse IP.
  Large exprès : plusieurs étudiants d'un même réseau (campus) partagent la même IP."""
  scope = 'auth'
  rate = '60/min'


class EmailRateThrottle(AnonRateThrottle):
  """Routes qui déclenchent l'envoi d'un e-mail : 10 appels/min par adresse IP."""
  scope = 'auth_email'
  rate = '10/min'


# --------------------------------------------------------------------------
# Authentification
# --------------------------------------------------------------------------

class LoginView(TokenObtainPairView):
  """POST /api/auth/login/ — {username, password, espace?}.

  Avec la double authentification (défaut) : envoie un code par e-mail et répond
  {requires_2fa: true, mfa_token, email, expires_in}. Les jetons JWT sont délivrés
  ensuite par POST /api/auth/verify-2fa/.
  Sans double authentification (TWO_FACTOR_ENABLED=False) : {access, refresh, user}."""
  serializer_class = LoginSerializer
  throttle_classes = [AuthRateThrottle]


class RegisterView(generics.CreateAPIView):
  """POST /api/utilisateurs/register/ : création d'un compte étudiant ou entreprise."""

  serializer_class = RegisterSerializer
  permission_classes = [permissions.AllowAny]
  authentication_classes = []
  throttle_classes = [AuthRateThrottle]

  def create(self, request, *args, **kwargs):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    data = dict(serializer.data)

    if deux_facteurs_actif():
      # Un code à 6 chiffres est envoyé par e-mail ; le compte reste « non vérifié »
      # tant que le code n'a pas été saisi (POST /api/auth/verify-2fa/).
      email_envoye = envoyer_code(user, REGISTER)
      data.update({
          'requires_2fa': True,
          'mfa_token': creer_mfa_token(user, REGISTER),
          'purpose': REGISTER,
          'email': masquer_email(user.email),
          'expires_in': validite_minutes() * 60,
          'detail': (
              "Compte créé. Un code de confirmation a été envoyé à votre adresse e-mail."
              if email_envoye else
              "Compte créé, mais l'e-mail n'a pas pu être envoyé. "
              "Demandez un nouveau code dans un instant."
          ),
      })
    else:
      envoyer_email_verification(user)
      data['detail'] = "Compte créé. Un e-mail de confirmation vous a été envoyé."
    return Response(data, status=status.HTTP_201_CREATED)


class Verify2FAView(generics.GenericAPIView):
  """POST /api/auth/verify-2fa/ — {mfa_token, code} -> {access, refresh, user}.

  Étape 2 de la connexion, ou confirmation de l'inscription (le compte est alors activé)."""
  serializer_class = Verify2FASerializer
  permission_classes = [permissions.AllowAny]
  authentication_classes = []
  throttle_classes = [AuthRateThrottle]

  def post(self, request):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return Response(Verify2FASerializer.jetons(user))


class Resend2FAView(generics.GenericAPIView):
  """POST /api/auth/resend-2fa/ — {mfa_token}. Renvoie un nouveau code (1 par minute max)."""
  serializer_class = Renvoyer2FASerializer
  permission_classes = [permissions.AllowAny]
  authentication_classes = []
  throttle_classes = [EmailRateThrottle]

  def post(self, request):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']
    if not envoyer_code(user, serializer.validated_data['purpose'], respecter_delai=True):
      raise EmailIndisponible()
    return Response({
        'detail': 'Un nouveau code a été envoyé à votre adresse e-mail.',
        'email': masquer_email(user.email),
        'expires_in': validite_minutes() * 60,
    })


class MeView(APIView):
  """GET /api/auth/me/ : utilisateur connecté (id, rôle, ...)."""

  def get(self, request):
    return Response(UserSerializer(request.user).data)


class VerifyEmailView(generics.GenericAPIView):
  """POST /api/auth/verify-email/ — {token}."""
  serializer_class = VerifyEmailSerializer
  permission_classes = [permissions.AllowAny]
  authentication_classes = []
  throttle_classes = [AuthRateThrottle]

  def post(self, request):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response({'detail': 'Adresse e-mail confirmée. Vous pouvez vous connecter.'})


class ResendVerificationView(generics.GenericAPIView):
  """POST /api/auth/resend-verification/ — {email}. Réponse identique que le compte existe ou non."""
  serializer_class = EmailSerializer
  permission_classes = [permissions.AllowAny]
  authentication_classes = []
  throttle_classes = [EmailRateThrottle]

  def post(self, request):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    for user in User.objects.filter(
        email__iexact=serializer.validated_data['email'], is_active=True, email_verifie=False
    ):
      envoyer_email_verification(user)
    return Response({'detail': "Si un compte non confirmé correspond à cet e-mail, un message a été envoyé."})


class PasswordResetRequestView(generics.GenericAPIView):
  """POST /api/auth/password-reset/ — {email}. Réponse identique que le compte existe ou non."""
  serializer_class = EmailSerializer
  permission_classes = [permissions.AllowAny]
  authentication_classes = []
  throttle_classes = [EmailRateThrottle]

  def post(self, request):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    for user in User.objects.filter(
        email__iexact=serializer.validated_data['email'], is_active=True
    ):
      envoyer_email_reinitialisation(user)
    return Response({'detail': "Si un compte correspond à cet e-mail, un message de réinitialisation a été envoyé."})


class PasswordResetConfirmView(generics.GenericAPIView):
  """POST /api/auth/password-reset-confirm/ — {uid, token, password}."""
  serializer_class = PasswordResetConfirmSerializer
  permission_classes = [permissions.AllowAny]
  authentication_classes = []
  throttle_classes = [AuthRateThrottle]

  def post(self, request):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response({'detail': 'Mot de passe modifié. Vous pouvez vous connecter.'})


# --------------------------------------------------------------------------
# Profils
# --------------------------------------------------------------------------

class ProfilEtudiantViewSet(viewsets.ModelViewSet):
  queryset = ProfilEtudiant.objects.all()
  serializer_class = ProfilEtudiantSerializer
  permission_classes = [permissions.IsAuthenticated, IsEtudiantOrAdmin]
  parser_classes = (MultiPartParser, FormParser)

  def get_queryset(self):
    user = self.request.user
    if user.is_staff:
      return ProfilEtudiant.objects.select_related('user').order_by('user__username')
    return ProfilEtudiant.objects.select_related('user').filter(user=user).order_by('id')

  def perform_create(self, serializer):
    if ProfilEtudiant.objects.filter(user=self.request.user).exists():
      raise ValidationError('Un profil étudiant existe déjà pour cet utilisateur.')
    serializer.save(utilisateur=self.request.user)

  @action(
      detail=False, methods=['get', 'put', 'patch'], url_path='me',
      permission_classes=[permissions.IsAuthenticated, IsEtudiant],
  )
  def me(self, request):
    """GET/PATCH /api/utilisateurs/profils-etudiants/me/ : mon profil (créé s'il manque)."""
    profil, _ = ProfilEtudiant.objects.select_related('user').get_or_create(user=request.user)
    if request.method == 'GET':
      return Response(self.get_serializer(profil).data)
    serializer = self.get_serializer(profil, data=request.data, partial=request.method == 'PATCH')
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


class EntreprisePagination(PageNumberPagination):
  # Permet au front de charger toute la liste des entreprises : ?page_size=100
  page_size_query_param = 'page_size'
  max_page_size = 100


ACTIONS_PUBLIQUES = ('list', 'retrieve')


class ProfilEntrepriseViewSet(viewsets.ModelViewSet):
  """Annuaire des entreprises : consultation ouverte à tous (même sans compte),
  création / modification réservées à l'entreprise concernée ou à un admin."""

  queryset = ProfilEntreprise.objects.select_related('user').order_by('nom_entreprise')
  serializer_class = ProfilEntrepriseSerializer
  parser_classes = (MultiPartParser, FormParser)
  pagination_class = EntreprisePagination
  filter_backends = [DjangoFilterBackend]
  filterset_class = ProfilEntrepriseFilter  # ?secteur= ?nom_entreprise= ?q=

  def get_authenticators(self):
    # Un token absent ou expiré n'empêche pas de consulter l'annuaire
    action = self.action_map.get(self.request.method.lower())
    if action in ACTIONS_PUBLIQUES:
      return [JWTAuthenticationOptionnelle()]
    return super().get_authenticators()

  def get_throttles(self):
    if self.action in ACTIONS_PUBLIQUES:
      return [ProfilsPublicsThrottle()]
    return super().get_throttles()

  def get_queryset(self):
    queryset = ProfilEntreprise.objects.select_related('user').order_by('nom_entreprise')
    if self.action in ACTIONS_PUBLIQUES:
      aujourdhui = timezone.localdate()
      queryset = queryset.filter(user__is_active=True).annotate(
          nb_offres_ouvertes=Count(
              'user__offres_publier', distinct=True,
              filter=Q(user__offres_publier__active=True, user__offres_publier__date_limite__gte=aujourdhui),
          )
      )
    return queryset

  def get_serializer_class(self):
    # Fiche publique (sans e-mail ni identifiant) pour la consultation ;
    # fiche complète pour le propriétaire (/me/) et les modifications.
    if self.action in ACTIONS_PUBLIQUES:
      return ProfilEntreprisePublicSerializer
    return ProfilEntrepriseSerializer

  def get_permissions(self):
    if self.action in ACTIONS_PUBLIQUES:
      permission_classes = [permissions.AllowAny]
    else:
      # Seule l'entreprise concernée ou un admin peut créer/modifier/supprimer
      permission_classes = [permissions.IsAuthenticated, IsEntrepriseOrAdmin]
    return [permission() for permission in permission_classes]

  def perform_create(self, serializer):
    if ProfilEntreprise.objects.filter(user=self.request.user).exists():
      raise ValidationError('Un profil entreprise existe déjà pour cet utilisateur.')
    # Associe automatiquement le profil à l'utilisateur connecté
    serializer.save(user=self.request.user)

  @action(
      detail=False, methods=['get', 'put', 'patch'], url_path='me',
      permission_classes=[permissions.IsAuthenticated, IsEntrepriseOrAdmin],
  )
  def me(self, request):
    """GET/PATCH /api/utilisateurs/profils-entreprises/me/ : le profil de mon entreprise."""
    try:
      profil = ProfilEntreprise.objects.select_related('user').get(user=request.user)
    except ProfilEntreprise.DoesNotExist:
      return Response({'detail': "Aucun profil entreprise pour ce compte."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == 'GET':
      return Response(self.get_serializer(profil).data)
    serializer = self.get_serializer(profil, data=request.data, partial=request.method == 'PATCH')
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


class EtudiantPublicViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
  """Annuaire public des étudiants : GET /api/utilisateurs/etudiants/ (même sans compte).

  Ne montre que les étudiants dont le profil est public (par défaut) et renseigné, et
  uniquement : prénom + initiale, formation, niveau, compétences. Jamais e-mail, téléphone, CV.
  Filtres : ?formation= ?niveau_etudes= ?competences= ?q=  — tri : ?ordering=-date_Mise_a_jour
  """

  serializer_class = ProfilEtudiantPublicSerializer
  permission_classes = [permissions.AllowAny]
  authentication_classes = [JWTAuthenticationOptionnelle]
  throttle_classes = [ProfilsPublicsThrottle]
  pagination_class = EntreprisePagination
  filter_backends = [DjangoFilterBackend, OrderingFilter]
  filterset_class = EtudiantPublicFilter
  ordering_fields = ['date_Mise_a_jour', 'formation']
  ordering = ['-date_Mise_a_jour']

  def get_queryset(self):
    return (
        ProfilEtudiant.objects.select_related('user')
        .filter(profil_public=True, user__is_active=True, user__role='ETUDIANT')
        .filter(Q(formation__gt='') | Q(competences__gt=''))  # ignore les profils vides
        .order_by('-date_Mise_a_jour')
    )

