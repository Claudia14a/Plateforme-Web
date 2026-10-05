from rest_framework import permissions


class IsEtudiant(permissions.BasePermission):
  """Réservé aux comptes ayant le rôle ETUDIANT."""

  def has_permission(self, request, view):
    return bool(
        request.user and request.user.is_authenticated and request.user.role == 'ETUDIANT'
    )


class IsEntreprise(permissions.BasePermission):
  """Réservé aux comptes ayant le rôle ENTREPRISE."""

  def has_permission(self, request, view):
    return bool(
        request.user and request.user.is_authenticated and request.user.role == 'ENTREPRISE'
    )


class IsEtudiantOrAdmin(permissions.BasePermission):
  """Permet l'accès uniquement aux utilisateurs ayant le rôle ETUDIANT ou ADMIN."""

  def has_permission(self, request, view):
    return (
        request.user
        and request.user.is_authenticated
        and (request.user.role == 'ETUDIANT' or request.user.is_staff)
    )

  def has_object_permission(self, request, view, obj):
    if request.user.is_staff:
      return True
    return obj.user == request.user


class IsEntrepriseOrAdmin(permissions.BasePermission):
  """Permet l'accès uniquement aux utilisateurs ayant le rôle ENTREPRISE ou ADMIN.

  Au niveau objet, le propriétaire est `obj.user` (ProfilEntreprise)
  ou `obj.entreprise` (OffreStage).
  """

  def has_permission(self, request, view):
    return (
        request.user
        and request.user.is_authenticated
        and (request.user.role == 'ENTREPRISE' or request.user.is_staff)
    )

  def has_object_permission(self, request, view, obj):
    if request.user.is_staff:
      return True
    proprietaire = getattr(obj, 'user', None) or getattr(obj, 'entreprise', None)
    return proprietaire == request.user
