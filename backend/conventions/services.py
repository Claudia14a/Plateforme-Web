"""Logique métier des conventions : création automatique, génération du PDF,
circuit de validation, attestation. Toutes les actions sont tracées dans le journal d'audit
et notifient les personnes concernées."""
import calendar
import datetime

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from administration import audit
from conventions import pdf
from conventions.models import Convention
from notifications.services import notifier, notifier_admins


class TransitionInvalide(Exception):
  """Action impossible dans l'état actuel de la convention."""


# --- Dates automatiques ---------------------------------------------------------

def ajouter_mois(d, n):
  mois = d.month - 1 + n
  annee = d.year + mois // 12
  mois = mois % 12 + 1
  return datetime.date(annee, mois, min(d.day, calendar.monthrange(annee, mois)[1]))


def date_debut_par_defaut(aujourdhui=None):
  """Premier lundi situé au moins 14 jours après aujourd'hui."""
  d = (aujourdhui or timezone.localdate()) + datetime.timedelta(days=14)
  return d + datetime.timedelta(days=(7 - d.weekday()) % 7)


def date_fin_pour(date_debut, duree_mois):
  return ajouter_mois(date_debut, duree_mois) - datetime.timedelta(days=1)


# --- Contexte commun ------------------------------------------------------------

def _contexte(convention):
  c = convention.candidature
  profil = getattr(c.offre.entreprise, 'profil_entreprise', None)
  return {
      'convention_id': convention.pk,
      'numero': convention.numero or convention.pk,
      'candidature_id': c.pk,
      'offre_titre': c.offre.titre,
      'etudiant_nom': c.etudiant.get_full_name() or c.etudiant.username,
      'entreprise_nom': profil.nom_entreprise if profil else c.offre.entreprise.username,
  }


def _parties(convention):
  c = convention.candidature
  return c.etudiant, c.offre.entreprise


# --- PDF -----------------------------------------------------------------------

def regenerer_pdf(convention):
  """(Re)génère le PDF à partir des données actuelles et remplace l'ancien fichier."""
  if not convention.numero:
    convention.numero = f'CONV-{timezone.localdate().year}-{convention.pk:05d}'
  contenu = pdf.construire_convention(convention)
  ancien = convention.fichier.name if convention.fichier else None
  convention.fichier.save(f'convention_{convention.numero}.pdf', ContentFile(contenu), save=False)
  convention.save()
  if ancien and ancien != convention.fichier.name:
    try:
      convention.fichier.storage.delete(ancien)
    except Exception:
      pass
  return convention


# --- Création automatique -----------------------------------------------------

@transaction.atomic
def creer_convention(candidature, date_debut=None, acteur=None):
  """Crée la convention d'une candidature acceptée et génère son PDF.
  Retourne (convention, creee). Sans effet si elle existe déjà."""
  existante = Convention.objects.filter(candidature=candidature).first()
  if existante:
    return existante, False

  offre = candidature.offre
  debut = date_debut or date_debut_par_defaut()
  convention = Convention.objects.create(
      candidature=candidature,
      sujet=offre.titre,
      missions=offre.description,
      lieu=offre.ville,
      date_debut=debut,
      date_fin=date_fin_pour(debut, offre.duree_mois),
  )
  regenerer_pdf(convention)
  audit.enregistrer(acteur, 'CONVENTION_CREEE', convention, {
      'candidature': candidature.pk, 'date_debut': str(convention.date_debut),
      'date_fin': str(convention.date_fin),
  })
  notifier_admins('CONVENTION_A_TRAITER', **_contexte(convention))
  return convention, True


# --- Modification (tant que non validée) -----------------------------------

CHAMPS_MODIFIABLES = ('sujet', 'missions', 'lieu', 'date_debut', 'date_fin')


def modifier(convention, donnees, acteur=None):
  if not convention.est_modifiable:
    raise TransitionInvalide(
        "Une convention validée ou signée ne peut plus être modifiée."
    )
  changements = {}
  for champ in CHAMPS_MODIFIABLES:
    if champ in donnees and donnees[champ] != getattr(convention, champ):
      changements[champ] = str(donnees[champ])
      setattr(convention, champ, donnees[champ])
  if convention.date_debut and convention.date_fin and convention.date_fin <= convention.date_debut:
    raise TransitionInvalide('La date de fin doit être postérieure à la date de début.')
  if changements:
    regenerer_pdf(convention)
    audit.enregistrer(acteur, 'CONVENTION_MODIFIEE', convention, {'champs': changements})
  return convention


# --- Circuit de validation ---------------------------------------------------

def _exiger(convention, statut_attendu, verbe):
  if convention.statut != statut_attendu:
    raise TransitionInvalide(
        f"Impossible de {verbe} : la convention est « {convention.get_statut_display()} »."
    )


@transaction.atomic
def soumettre(convention, acteur=None):
  """BROUILLON -> EN_ATTENTE"""
  _exiger(convention, Convention.Statut.BROUILLON, 'soumettre')
  if not (convention.date_debut and convention.date_fin and convention.sujet):
    raise TransitionInvalide('Sujet et dates sont obligatoires avant de soumettre.')
  convention.statut = Convention.Statut.EN_ATTENTE
  convention.motif_rejet = ''
  regenerer_pdf(convention)
  audit.enregistrer(acteur, 'CONVENTION_SOUMISE', convention)
  return convention


@transaction.atomic
def rejeter(convention, motif, acteur=None):
  """EN_ATTENTE -> BROUILLON (retour pour correction, avec motif)"""
  _exiger(convention, Convention.Statut.EN_ATTENTE, 'rejeter')
  if not (motif or '').strip():
    raise TransitionInvalide('Le motif du rejet est obligatoire.')
  convention.statut = Convention.Statut.BROUILLON
  convention.motif_rejet = motif.strip()
  convention.save()
  audit.enregistrer(acteur, 'CONVENTION_REJETEE', convention, {'motif': motif.strip()})
  return convention


@transaction.atomic
def valider(convention, acteur=None):
  """EN_ATTENTE -> VALIDEE : le PDF devient définitif (sans filigrane) et téléchargeable."""
  _exiger(convention, Convention.Statut.EN_ATTENTE, 'valider')
  convention.statut = Convention.Statut.VALIDEE
  convention.date_validation = timezone.now()
  convention.valide_par = acteur if getattr(acteur, 'is_authenticated', False) else None
  regenerer_pdf(convention)
  audit.enregistrer(acteur, 'CONVENTION_VALIDEE', convention)
  etudiant, entreprise = _parties(convention)
  for destinataire in (etudiant, entreprise):
    notifier(destinataire, 'CONVENTION_PRETE', **_contexte(convention))
  return convention


@transaction.atomic
def signer(convention, acteur=None, fichier_signe=None):
  """VALIDEE -> SIGNEE. Un scan de la convention signée peut être joint (PDF)."""
  _exiger(convention, Convention.Statut.VALIDEE, 'marquer comme signée')
  convention.statut = Convention.Statut.SIGNEE
  convention.date_signature = timezone.now()
  if fichier_signe is not None:
    convention.fichier_signe.save('convention_signee.pdf', fichier_signe, save=False)
  regenerer_pdf(convention)
  audit.enregistrer(acteur, 'CONVENTION_SIGNEE', convention, {'scan_joint': fichier_signe is not None})
  etudiant, entreprise = _parties(convention)
  for destinataire in (etudiant, entreprise):
    notifier(destinataire, 'CONVENTION_SIGNEE', **_contexte(convention))
  return convention


# --- Attestation de stage ------------------------------------------------------

@transaction.atomic
def emettre_attestation(convention, acteur=None):
  """Génère l'attestation de fin de stage (convention signée et stage terminé)."""
  if convention.statut != Convention.Statut.SIGNEE:
    raise TransitionInvalide("L'attestation n'est possible que pour une convention signée.")
  if not convention.date_fin or convention.date_fin > timezone.localdate():
    raise TransitionInvalide(
        f"Le stage n'est pas terminé (fin prévue le {convention.date_fin:%d/%m/%Y})."
    )
  if convention.attestation:
    raise TransitionInvalide("L'attestation a déjà été délivrée.")
  contenu = pdf.construire_attestation(convention)
  convention.attestation.save(
      f'attestation_{convention.numero}.pdf', ContentFile(contenu), save=False
  )
  convention.date_attestation = timezone.now()
  convention.save()
  audit.enregistrer(acteur, 'ATTESTATION_EMISE', convention)
  notifier(convention.candidature.etudiant, 'ATTESTATION_DISPONIBLE', **_contexte(convention))
  return convention
