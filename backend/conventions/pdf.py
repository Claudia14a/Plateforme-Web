"""Génération des PDF (convention et attestation) avec ReportLab.

La convention est construite à partir d'un TEMPLATE de clauses (TEMPLATE_ARTICLES)
dont les {champs} sont remplis automatiquement avec les données de l'étudiant,
de l'entreprise, de l'offre et les dates. Pour changer le texte juridique,
il suffit de modifier TEMPLATE_ARTICLES ci-dessous.
"""
import io
from xml.sax.saxutils import escape

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# --- Template de la convention ------------------------------------------------

TEMPLATE_PARTIES = [
    "<b>L'établissement d'enseignement :</b> {univ_nom}{univ_adresse_txt}, "
    "ci-après dénommé « l'Université ».",
    "<b>L'entreprise d'accueil :</b> {entreprise_nom} (secteur : {secteur}), "
    "adresse : {entreprise_adresse}, tél. : {entreprise_tel}, "
    "ci-après dénommée « l'Entreprise ».",
    "<b>L'étudiant(e) :</b> {etudiant_nom}, {etudiant_statut}, "
    "e-mail : {etudiant_email}, tél. : {etudiant_tel}, "
    "ci-après dénommé(e) « le Stagiaire ».",
]

TEMPLATE_ARTICLES = [
    ("Article 1 - Objet",
     "La présente convention a pour objet de définir les conditions dans lesquelles "
     "le Stagiaire effectuera un stage au sein de l'Entreprise, sur le sujet suivant : "
     "« {sujet} »."),
    ("Article 2 - Missions",
     "Les missions confiées au Stagiaire sont les suivantes : {missions}"),
    ("Article 3 - Durée du stage",
     "Le stage se déroulera du <b>{date_debut}</b> au <b>{date_fin}</b>, "
     "soit une durée de {duree_mois} mois."),
    ("Article 4 - Lieu du stage", "Le stage se déroule à : {lieu}."),
    ("Article 5 - Encadrement",
     "L'Entreprise désigne un tuteur chargé d'accueillir, d'encadrer et de conseiller "
     "le Stagiaire. L'Université désigne un enseignant référent chargé du suivi pédagogique."),
    ("Article 6 - Obligations du Stagiaire",
     "Le Stagiaire s'engage à respecter le règlement intérieur et les horaires de "
     "l'Entreprise, à observer la confidentialité des informations dont il a connaissance "
     "et à fournir à l'Université les documents demandés."),
    ("Article 7 - Obligations de l'Entreprise",
     "L'Entreprise s'engage à confier au Stagiaire des activités en rapport avec le sujet "
     "du stage, à l'encadrer et à l'évaluer à la fin du stage."),
    ("Article 8 - Évaluation et attestation",
     "À l'issue du stage, l'Entreprise évalue le Stagiaire et lui remet une attestation de stage."),
    ("Article 9 - Interruption du stage",
     "Toute interruption ou rupture anticipée du stage doit être signalée à l'Université "
     "et fait l'objet d'un accord écrit des trois parties."),
]

# --- Styles -------------------------------------------------------------------

ACCENT = colors.HexColor('#1F4E79')
S_TITRE = ParagraphStyle('titre', fontName='Helvetica-Bold', fontSize=18, leading=22,
                         alignment=TA_CENTER, textColor=ACCENT, spaceAfter=4)
S_SOUS_TITRE = ParagraphStyle('sous', fontName='Helvetica', fontSize=10, leading=13,
                              alignment=TA_CENTER, textColor=colors.HexColor('#555555'), spaceAfter=14)
S_TEXTE = ParagraphStyle('texte', fontName='Helvetica', fontSize=10.5, leading=15,
                         alignment=TA_JUSTIFY, spaceAfter=6)
S_ARTICLE = ParagraphStyle('article', fontName='Helvetica-Bold', fontSize=11, leading=14,
                           textColor=ACCENT, spaceBefore=8, spaceAfter=3)
S_CENTRE = ParagraphStyle('centre', parent=S_TEXTE, alignment=TA_CENTER)
S_SIGN = ParagraphStyle('sign', fontName='Helvetica-Bold', fontSize=10, alignment=TA_CENTER)
S_SIGN_PETIT = ParagraphStyle('signp', fontName='Helvetica', fontSize=8.5, leading=11,
                              alignment=TA_CENTER, textColor=colors.HexColor('#555555'))


def _e(valeur, defaut='non renseigné'):
  texte = str(valeur).strip() if valeur not in (None, '') else ''
  return escape(texte) if texte else defaut


def _date(d):
  return d.strftime('%d/%m/%Y') if d else '...'


def _statut_etudiant(profil):
  """« étudiant(e) en Master Réseaux (Bac+5) », ou simplement « étudiant(e) » si le profil est vide."""
  formation = (profil.formation or '').strip() if profil else ''
  niveau = (profil.niveau_etudes or '').strip() if profil else ''
  if not formation:
    return 'étudiant(e)'
  return f"étudiant(e) en {escape(formation)}" + (f' ({escape(niveau)})' if niveau else '')


def _contexte(convention):
  c = convention.candidature
  offre = c.offre
  etudiant = c.etudiant
  p_etu = getattr(etudiant, 'profil_etudiant', None)
  p_ent = getattr(offre.entreprise, 'profil_entreprise', None)
  univ_adresse = getattr(settings, 'UNIVERSITE_ADRESSE', '')
  return {
      'univ_nom': _e(getattr(settings, 'UNIVERSITE_NOM', 'Université')),
      'univ_adresse_txt': f', {escape(univ_adresse)}' if univ_adresse else '',
      'univ_ville': escape(getattr(settings, 'UNIVERSITE_VILLE', '') or ''),
      'entreprise_nom': _e(p_ent.nom_entreprise if p_ent else offre.entreprise.username),
      'secteur': _e(p_ent.secteur if p_ent else None),
      'entreprise_adresse': _e(p_ent.adresse if p_ent else None),
      'entreprise_tel': _e(p_ent.telephone if p_ent else None),
      'etudiant_nom': _e(etudiant.get_full_name() or etudiant.username),
      'etudiant_email': _e(etudiant.email),
      'etudiant_tel': _e(p_etu.telephone if p_etu else None),
      'etudiant_statut': _statut_etudiant(p_etu),
      'sujet': _e(convention.sujet or offre.titre),
      'missions': _e(convention.missions or offre.description),
      'lieu': _e(convention.lieu or offre.ville),
      'date_debut': _date(convention.date_debut),
      'date_fin': _date(convention.date_fin),
      'duree_mois': offre.duree_mois,
      'numero': _e(convention.numero or convention.pk),
      'date_edition': _date(timezone.localdate()),
  }


def _filigrane_et_pied(texte_filigrane, numero):
  def dessiner(canvas, doc):
    canvas.saveState()
    if texte_filigrane:
      canvas.setFillColor(colors.Color(0.92, 0.92, 0.92))
      canvas.setFont('Helvetica-Bold', 96)
      canvas.translate(A4[0] / 2, A4[1] / 2)
      canvas.rotate(45)
      canvas.drawCentredString(0, 0, texte_filigrane)
    canvas.restoreState()
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.HexColor('#777777'))
    canvas.drawCentredString(A4[0] / 2, 1.2 * cm, f'{numero} - page {doc.page}')
    canvas.restoreState()
  return dessiner


def _bloc_signatures(titres, hauteur=3 * cm):
  cellules = [[Paragraph(t, S_SIGN) for t in titres],
              [Paragraph('Lu et approuvé<br/>Date, signature et cachet', S_SIGN_PETIT)] * len(titres),
              [''] * len(titres)]
  tableau = Table(cellules, colWidths=[(A4[0] - 4 * cm) / len(titres)] * len(titres),
                  rowHeights=[0.7 * cm, 1 * cm, hauteur])
  tableau.setStyle(TableStyle([
      ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#999999')),
      ('INNERGRID', (0, 0), (-1, -1), 0.6, colors.HexColor('#999999')),
      ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
  ]))
  return tableau


def _document(titre_meta):
  tampon = io.BytesIO()
  doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                          topMargin=2 * cm, bottomMargin=2 * cm, title=titre_meta,
                          author=getattr(settings, 'UNIVERSITE_NOM', 'Université'))
  return doc, tampon


# --- Convention ---------------------------------------------------------------

def construire_convention(convention):
  """Retourne le PDF (bytes) de la convention, rempli à partir des données."""
  ctx = _contexte(convention)
  doc, tampon = _document(f"Convention de stage {convention.numero or ''}")
  statut = convention.statut

  mention = {
      'BROUILLON': 'Projet - en cours de préparation',
      'EN_ATTENTE': "Projet - en attente de validation par l'administration",
      'VALIDEE': f"Validée par l'administration le {_date(convention.date_validation)}",
      'SIGNEE': f"Signée le {_date(convention.date_signature)}",
  }[statut]

  histoire = [
      Paragraph('CONVENTION DE STAGE', S_TITRE),
      Paragraph(f"N° {ctx['numero']} - {escape(mention)}", S_SOUS_TITRE),
      Paragraph('Entre les soussignés :', S_TEXTE),
  ]
  histoire += [Paragraph(t.format(**ctx), S_TEXTE) for t in TEMPLATE_PARTIES]
  histoire.append(Paragraph('Il a été convenu ce qui suit :', S_TEXTE))
  for titre, texte in TEMPLATE_ARTICLES:
    histoire.append(KeepTogether([Paragraph(titre, S_ARTICLE), Paragraph(texte.format(**ctx), S_TEXTE)]))

  lieu_date = f"Fait à {ctx['univ_ville']}, le " if ctx['univ_ville'] else 'Fait le '
  histoire.append(Spacer(1, 10))
  histoire.append(KeepTogether([
      Paragraph(f"{lieu_date}{ctx['date_edition']}, en trois exemplaires.", S_CENTRE),
      Spacer(1, 6),
      _bloc_signatures(['Le Stagiaire', "Pour l'Entreprise", "Pour l'Université"]),
  ]))

  filigrane = None if statut in ('VALIDEE', 'SIGNEE') else 'PROJET'
  rendu = _filigrane_et_pied(filigrane, ctx['numero'])
  doc.build(histoire, onFirstPage=rendu, onLaterPages=rendu)
  return tampon.getvalue()


# --- Attestation de stage -----------------------------------------------------

def construire_attestation(convention):
  ctx = _contexte(convention)
  doc, tampon = _document(f"Attestation de stage {convention.numero or ''}")
  lieu_date = f"Fait à {ctx['univ_ville']}, le " if ctx['univ_ville'] else 'Fait le '

  corps = (
      f"Nous soussignés, <b>{ctx['entreprise_nom']}</b>, attestons que "
      f"<b>{ctx['etudiant_nom']}</b>, {ctx['etudiant_statut']} "
      f"à {ctx['univ_nom']}, a effectué un stage au sein de notre entreprise "
      f"du <b>{ctx['date_debut']}</b> au <b>{ctx['date_fin']}</b>, "
      f"soit une durée de {ctx['duree_mois']} mois, sur le sujet suivant : « {ctx['sujet']} »."
  )
  histoire = [
      Spacer(1, 1.5 * cm),
      Paragraph('ATTESTATION DE STAGE', S_TITRE),
      Paragraph(f"Référence : convention n° {ctx['numero']}", S_SOUS_TITRE),
      Spacer(1, 1 * cm),
      Paragraph(corps, ParagraphStyle('corps', parent=S_TEXTE, fontSize=12, leading=19)),
      Spacer(1, 0.4 * cm),
      Paragraph("Cette attestation est délivrée à l'intéressé(e) pour servir et valoir ce que de droit.",
                ParagraphStyle('corps2', parent=S_TEXTE, fontSize=12, leading=19)),
      Spacer(1, 1.2 * cm),
      Paragraph(f"{lieu_date}{ctx['date_edition']}.", S_CENTRE),
      Spacer(1, 0.4 * cm),
      _bloc_signatures(["Pour l'Entreprise (signature et cachet)"], hauteur=3.5 * cm),
  ]
  rendu = _filigrane_et_pied(None, ctx['numero'])
  doc.build(histoire, onFirstPage=rendu, onLaterPages=rendu)
  return tampon.getvalue()
