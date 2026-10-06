"""Calculs du tableau de bord et des statistiques (agrégations en base)."""
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.db.models.functions import Coalesce, Lower, Trim
from django.utils import timezone

from candidatures.models import Candidature
from conventions.models import Convention
from offres.models import OffreStage

User = get_user_model()


def _jours(duree):
  return round(duree.total_seconds() / 86400, 2) if duree else None


def _pourcentage(partie, total):
  return round(100 * partie / total, 1) if total else None


def _stage_en_cours_q(prefixe=''):
  """Convention signée dont la période de stage contient la date du jour."""
  aujourdhui = timezone.localdate()
  return Q(**{
      f'{prefixe}statut': Convention.Statut.SIGNEE,
      f'{prefixe}date_debut__lte': aujourdhui,
      f'{prefixe}date_fin__gte': aujourdhui,
  })


def tableau_de_bord():
  aujourdhui = timezone.localdate()

  par_role = {r: 0 for r, _ in User.ROLE_CHOICES}
  par_role.update({x['role']: x['n'] for x in User.objects.values('role').annotate(n=Count('id'))})

  offres = OffreStage.objects.aggregate(
      total=Count('id'),
      ouvertes=Count('id', filter=Q(active=True, date_limite__gte=aujourdhui)),
      cloturees=Count('id', filter=Q(active=False)),
      expirees=Count('id', filter=Q(active=True, date_limite__lt=aujourdhui)),
  )

  par_statut_cand = {s: 0 for s, _ in Candidature.Statut.choices}
  par_statut_cand.update({
      x['statut']: x['n'] for x in Candidature.objects.values('statut').annotate(n=Count('id'))
  })

  par_statut_conv = {s: 0 for s, _ in Convention.Statut.choices}
  par_statut_conv.update({
      x['statut']: x['n'] for x in Convention.objects.values('statut').annotate(n=Count('id'))
  })

  signees = Convention.objects.filter(statut=Convention.Statut.SIGNEE)
  stages = {
      'en_cours': signees.filter(date_debut__lte=aujourdhui, date_fin__gte=aujourdhui).count(),
      'a_venir': signees.filter(date_debut__gt=aujourdhui).count(),
      'termines': signees.filter(date_fin__lt=aujourdhui).count(),
  }

  return {
      'utilisateurs': {
          'total': sum(par_role.values()),
          'par_role': par_role,
          'comptes_desactives': User.objects.filter(is_active=False).count(),
          'emails_non_verifies': User.objects.filter(email_verifie=False).count(),
      },
      'offres': offres,
      'candidatures': {'total': sum(par_statut_cand.values()), 'par_statut': par_statut_cand},
      'conventions': {
          'total': sum(par_statut_conv.values()),
          'par_statut': par_statut_conv,
          'a_traiter': par_statut_conv['BROUILLON'] + par_statut_conv['EN_ATTENTE'],
      },
      # « en cours » = convention SIGNEE dont les dates encadrent aujourd'hui
      'stages': stages,
  }


def statistiques():
  aujourdhui = timezone.localdate()
  decidees = Candidature.objects.exclude(date_decision=None)
  delai = ExpressionWrapper(F('date_decision') - F('date_candidature'), output_field=DurationField())
  acceptees = Candidature.objects.filter(statut=Candidature.Statut.ACCEPTEE).count()
  refusees = Candidature.objects.filter(statut=Candidature.Statut.REFUSEE).count()
  total_candidatures = Candidature.objects.count()

  delai_validation = ExpressionWrapper(
      F('date_validation') - F('date_creation'), output_field=DurationField()
  )
  conventions = Convention.objects.count()
  signees = Convention.objects.filter(statut=Convention.Statut.SIGNEE).count()

  globales = {
      'candidatures_total': total_candidatures,
      'taux_acceptation_pct': _pourcentage(acceptees, acceptees + refusees),  # parmi les candidatures traitées
      'taux_traitement_pct': _pourcentage(acceptees + refusees, total_candidatures),
      'temps_moyen_traitement_candidature_jours': _jours(decidees.aggregate(m=Avg(delai))['m']),
      'temps_moyen_validation_convention_jours': _jours(
          Convention.objects.exclude(date_validation=None).aggregate(m=Avg(delai_validation))['m']
      ),
      'taux_conventions_signees_pct': _pourcentage(signees, conventions),
  }

  entreprises = (
      User.objects.filter(role='ENTREPRISE')
      .annotate(
          nom=Coalesce('profil_entreprise__nom_entreprise', 'username'),
          nb_offres=Count('offres_publier', distinct=True),
          nb_candidatures=Count('offres_publier__candidatures', distinct=True),
          nb_acceptees=Count(
              'offres_publier__candidatures', distinct=True,
              filter=Q(offres_publier__candidatures__statut=Candidature.Statut.ACCEPTEE),
          ),
          stages_en_cours=Count(
              'offres_publier__candidatures__convention', distinct=True,
              filter=_stage_en_cours_q('offres_publier__candidatures__convention__'),
          ),
      )
      .order_by('-nb_candidatures', 'nom')
  )
  par_entreprise = [
      {
          'entreprise_id': e.id, 'entreprise': e.nom, 'offres': e.nb_offres,
          'candidatures': e.nb_candidatures, 'acceptees': e.nb_acceptees,
          'stages_en_cours': e.stages_en_cours,
          'taux_acceptation_pct': _pourcentage(e.nb_acceptees, e.nb_candidatures),
      }
      for e in entreprises
  ]

  domaines = (
      OffreStage.objects.annotate(d=Lower(Trim('domaine'))).values('d')
      .annotate(
          nb_offres=Count('id', distinct=True),
          nb_candidatures=Count('candidatures', distinct=True),
          nb_acceptees=Count(
              'candidatures', distinct=True,
              filter=Q(candidatures__statut=Candidature.Statut.ACCEPTEE),
          ),
          stages_en_cours=Count(
              'candidatures__convention', distinct=True,
              filter=_stage_en_cours_q('candidatures__convention__'),
          ),
      )
      .order_by('-nb_candidatures', 'd')
  )
  par_domaine = [
      {
          'domaine': x['d'].capitalize(), 'offres': x['nb_offres'],
          'candidatures': x['nb_candidatures'], 'acceptees': x['nb_acceptees'],
          'stages_en_cours': x['stages_en_cours'],
          'taux_acceptation_pct': _pourcentage(x['nb_acceptees'], x['nb_candidatures']),
      }
      for x in domaines
  ]
  return {'globales': globales, 'par_entreprise': par_entreprise, 'par_domaine': par_domaine}
