#!/usr/bin/env bash
# =============================================================================
#  Test de toutes les fonctionnalités de l'API (utilisateurs, offres, candidatures,
#  conventions, administration, notifications).
#
#  Chaque test affiche la commande curl équivalente, puis ✔ ou ✘ selon le code
#  HTTP attendu. Les PDF générés sont enregistrés dans ./resultats_tests/
#
#  Utilisation (depuis le dossier backend, venv activé, serveur lancé) :
#     ADMIN_USER=admin ADMIN_PASS='votre-mot-de-passe' ./tester_api.sh            # tout
#     ADMIN_USER=admin ADMIN_PASS='...' ./tester_api.sh conventions               # jusqu'à une section
#  Sections : auth  offres  candidatures  conventions  administration  notifications
#  (les sections précédentes sont rejouées : elles préparent les données)
#
#  Double authentification : le code arrive par e-mail. Deux façons de le fournir :
#   - le saisir quand le script le demande (il s'affiche dans le terminal du serveur
#     si EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend) ;
#   - automatiquement : lancer le serveur avec
#         PYTHONUNBUFFERED=1 python manage.py runserver 2>&1 | tee serveur.log
#     puis exporter  CODE_COMMAND="grep -E '^ +[0-9]{6}$' serveur.log | tr -d ' ' | tail -1"
#
#  Le compte ADMIN doit avoir une adresse e-mail (nécessaire à la double authentification).
# =============================================================================

BASE="${BASE:-http://127.0.0.1:8000/api}"
PY="${PY:-python manage.py}"
MDP='Stages#Test2026'
TS=$(date +%s)
OK=0; KO=0
RES="resultats_tests"; mkdir -p "$RES"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
JSON=(-H 'Content-Type: application/json')
VERT=$'\e[32m'; ROUGE=$'\e[31m'; BLEU=$'\e[36m'; FIN=$'\e[0m'

printf '%%PDF-1.4\n%%fichier de test\n' > "$TMP/cv.pdf"
printf '%%PDF-1.4\n%%lettre de motivation\n' > "$TMP/lettre.pdf"
printf '%%PDF-1.4\n%%scan convention signee\n' > "$TMP/scan.pdf"
printf 'ceci n est pas un pdf' > "$TMP/faux.txt"

# ---------- utilitaires ------------------------------------------------------

jget() {  # lit un JSON sur stdin : jget results.0.id
  python3 -c "
import sys, json
try: d = json.load(sys.stdin)
except Exception: sys.exit(0)
for k in sys.argv[1].split('.'):
    if isinstance(d, list):
        try: d = d[int(k)]
        except Exception: d = None
    elif isinstance(d, dict): d = d.get(k)
    else: d = None
    if d is None: break
print('' if d is None else d)" "$1"
}

section() { echo; echo "${BLEU}============================================================${FIN}"; echo "${BLEU}  $1${FIN}"; echo "${BLEU}============================================================${FIN}"; }

verdict() {  # verdict "description" ATTENDU(S) CODE
  if [[ "|$2|" == *"|$3|"* ]]; then OK=$((OK+1)); echo "  ${VERT}✔ HTTP $3${FIN}"
  else KO=$((KO+1)); echo "  ${ROUGE}✘ HTTP $3 (attendu : $2)${FIN}"; fi
}

appel() {  # appel "description" CODE_ATTENDU METHODE /chemin JETON [options curl...]
  local desc="$1" attendu="$2" methode="$3" chemin="$4" jeton="$5"; shift 5
  local entete=(); [ -n "$jeton" ] && entete=(-H "Authorization: Bearer $jeton")
  local aff="curl -s -X $methode '$BASE$chemin'" a
  [ -n "$jeton" ] && aff+=" -H 'Authorization: Bearer \$TOKEN'"
  for a in "$@"; do case "$a" in -H|-d|-F) aff+=" $a";; *) aff+=" '$(echo "$a" | sed -E 's/"password":"[^"]*"/"password":"***"/g')'";; esac; done
  echo; echo "▶ $desc"; echo "  $aff"
  CODE=$(curl -s -o "$TMP/corps" -w '%{http_code}' -X "$methode" "${entete[@]}" "$@" "$BASE$chemin")
  CORPS=$(cat "$TMP/corps")
  echo "  ← $(echo "$CORPS" | head -c 260)"
  verdict "$desc" "$attendu" "$CODE"
}

telecharger() {  # telecharger "description" CODE_ATTENDU /chemin JETON fichier_local [pdf|csv]
  local desc="$1" attendu="$2" chemin="$3" jeton="$4" fichier="$5" type="${6:-pdf}"
  echo; echo "▶ $desc"; echo "  curl -s -H 'Authorization: Bearer \$TOKEN' -o $RES/$fichier '$BASE$chemin'"
  CODE=$(curl -s -o "$RES/$fichier" -w '%{http_code}' -H "Authorization: Bearer $jeton" "$BASE$chemin")
  if [ "$CODE" = "200" ]; then
    if [ "$type" = "pdf" ] && ! head -c 5 "$RES/$fichier" | grep -q '%PDF-'; then
      KO=$((KO+1)); echo "  ${ROUGE}✘ le fichier reçu n'est pas un PDF${FIN}"; return
    fi
    echo "  ← fichier enregistré : $RES/$fichier ($(wc -c < "$RES/$fichier") octets)"
  else rm -f "$RES/$fichier"; echo "  ← $CODE"; fi
  verdict "$desc" "$attendu" "$CODE"
}

lire_code() {  # retourne le code à 6 chiffres de la double authentification
  if [ -n "$CODE_COMMAND" ]; then sleep 1; eval "$CODE_COMMAND"; return; fi
  local c; read -r -p "  >> Code à 6 chiffres reçu par e-mail pour $1 (voir le terminal du serveur) : " c </dev/tty; echo "$c"
}

verifier_2fa() {  # verifier_2fa utilisateur mfa_token -> remplit ACCES, REFRESH
  local code; code=$(lire_code "$1")
  appel "Double authentification de $1 : saisie du code" 200 POST /auth/verify-2fa/ "" "${JSON[@]}" -d "{\"mfa_token\":\"$2\",\"code\":\"$code\"}"
  ACCES=$(echo "$CORPS" | jget access); REFRESH=$(echo "$CORPS" | jget refresh); UID_COURANT=$(echo "$CORPS" | jget user.id)
}

connexion() {  # connexion VARIABLE utilisateur motdepasse [espace]
  local var="$1" user="$2" pass="$3" espace="$4"
  appel "Connexion de $user${espace:+ (espace $espace)}" 200 POST /auth/login/ "" "${JSON[@]}" \
        -d "{\"username\":\"$user\",\"password\":\"$pass\"${espace:+,\"espace\":\"$espace\"}}"
  ACCES=$(echo "$CORPS" | jget access); REFRESH=$(echo "$CORPS" | jget refresh); UID_COURANT=$(echo "$CORPS" | jget user.id)
  if [ -z "$ACCES" ]; then
    local mfa; mfa=$(echo "$CORPS" | jget mfa_token)
    [ -z "$mfa" ] && { echo "  ${ROUGE}✘ ni jeton, ni double authentification dans la réponse${FIN}"; KO=$((KO+1)); return 1; }
    verifier_2fa "$user" "$mfa"
  fi
  printf -v "$var" '%s' "$ACCES"
}

inscrire() {  # inscrire VARIABLE utilisateur role [json supplémentaire]
  local var="$1" user="$2" role="$3" extra="$4"
  appel "Inscription de $user (rôle $role)" 201 POST /utilisateurs/register/ "" "${JSON[@]}" \
        -d "{\"username\":\"$user\",\"password\":\"$MDP\",\"email\":\"$user@example.com\",\"role\":\"$role\"$extra}"
  local mfa uid; mfa=$(echo "$CORPS" | jget mfa_token); uid=$(echo "$CORPS" | jget id)
  printf -v "ID_$var" '%s' "$uid"
  if [ -n "$mfa" ]; then
    verifier_2fa "$user" "$mfa"; printf -v "$var" '%s' "$ACCES"
  else  # double authentification désactivée : on marque l'e-mail comme vérifié puis on se connecte
    $PY shell -c "from utilisateurs.models import User; User.objects.filter(username='$user').update(email_verifie=True)" >/dev/null 2>&1
    connexion "$var" "$user" "$MDP"
  fi
}

jours() { date -d "+$1 days" +%F; }

# ---------- préparation ------------------------------------------------------

preparation() {
  section "0. PRÉPARATION : création des comptes de test"
  ETU_A="etudiantA$TS"; ETU_B="etudiantB$TS"; ENT="entreprise$TS"
  inscrire T_A "$ETU_A" ETUDIANT ',"first_name":"Aina","last_name":"Rakoto"'
  inscrire T_B "$ETU_B" ETUDIANT ',"first_name":"Bema","last_name":"Rabe"'
  inscrire T_ENT "$ENT" ENTREPRISE ',"nom_entreprise":"Entreprise Test","secteur":"Informatique"'
  if [ -z "$ADMIN_USER" ]; then read -r -p "Compte administrateur : " ADMIN_USER; fi
  if [ -z "$ADMIN_PASS" ]; then read -r -s -p "Mot de passe de $ADMIN_USER : " ADMIN_PASS; echo; fi
  connexion T_ADM "$ADMIN_USER" "$ADMIN_PASS" ADMIN
  ID_ADM="$UID_COURANT"
  [ -z "$T_ADM" ] && { echo "${ROUGE}Connexion admin impossible : arrêt.${FIN}"; bilan; exit 1; }
}

# ---------- 1. authentification et profils ------------------------------------

test_auth() {
  section "1. AUTHENTIFICATION, RÔLES ET PROFILS (utilisateurs)"
  appel "Mauvais mot de passe refusé" 401 POST /auth/login/ "" "${JSON[@]}" -d "{\"username\":\"$ETU_A\",\"password\":\"mauvais\"}"
  appel "Connexion refusée dans le mauvais espace (étudiant -> ENTREPRISE)" 403 POST /auth/login/ "" "${JSON[@]}" \
        -d "{\"username\":\"$ETU_A\",\"password\":\"$MDP\",\"espace\":\"ENTREPRISE\"}"
  appel "Inscription avec le rôle ADMIN refusée" 400 POST /utilisateurs/register/ "" "${JSON[@]}" \
        -d "{\"username\":\"pirate$TS\",\"password\":\"$MDP\",\"email\":\"pirate$TS@example.com\",\"role\":\"ADMIN\"}"
  appel "API sans token refusée" 401 GET /offres/offres/ ""

  # Double authentification : étape 1, mauvais code, renvoi trop rapide, bon code
  appel "2FA - étape 1 : identifiants corrects" 200 POST /auth/login/ "" "${JSON[@]}" -d "{\"username\":\"$ETU_A\",\"password\":\"$MDP\"}"
  local mfa; mfa=$(echo "$CORPS" | jget mfa_token)
  if [ -n "$mfa" ]; then
    echo "  (aucun jeton JWT à cette étape : seulement mfa_token)"
    appel "2FA - mauvais code refusé" 400 POST /auth/verify-2fa/ "" "${JSON[@]}" -d "{\"mfa_token\":\"$mfa\",\"code\":\"000000\"}"
    appel "2FA - renvoi du code trop rapproché refusé (1 par minute)" 429 POST /auth/resend-2fa/ "" "${JSON[@]}" -d "{\"mfa_token\":\"$mfa\"}"
    verifier_2fa "$ETU_A" "$mfa"; T_A="$ACCES"
  else
    echo "  (double authentification désactivée : étapes 2FA ignorées)"
    T_A="$(echo "$CORPS" | jget access)"
  fi
  local refresh="$REFRESH"
  appel "Utilisateur connecté et son rôle" 200 GET /auth/me/ "$T_A"
  appel "Renouvellement du token d'accès (refresh)" 200 POST /auth/refresh/ "" "${JSON[@]}" -d "{\"refresh\":\"$refresh\"}"
  appel "Mot de passe oublié (réponse neutre, e-mail dans le terminal du serveur)" 200 POST /auth/password-reset/ "" "${JSON[@]}" -d "{\"email\":\"$ETU_A@example.com\"}"
  appel "Mot de passe oublié avec e-mail inconnu : même réponse" 200 POST /auth/password-reset/ "" "${JSON[@]}" -d '{"email":"inconnu@example.com"}'

  appel "Étudiant : compléter son profil + CV PDF" 200 PATCH /utilisateurs/profils-etudiants/me/ "$T_A" \
        -F "formation=Master Réseaux" -F "niveau_etudes=Bac+5" -F "competences=Python, Django" -F "telephone=034 00 000 00" -F "cv=@$TMP/cv.pdf;type=application/pdf"
  appel "Étudiant : CV qui n'est pas un PDF refusé" 400 PATCH /utilisateurs/profils-etudiants/me/ "$T_A" -F "cv=@$TMP/faux.txt;type=application/pdf"
  appel "Entreprise : compléter son profil" 200 PATCH /utilisateurs/profils-entreprises/me/ "$T_ENT" \
        -F "description=Société de services numériques" -F "adresse=Antananarivo" -F "site_web=https://exemple.mg"
  appel "Liste des entreprises (pour un champ de formulaire)" 200 GET "/utilisateurs/profils-entreprises/?page_size=100" "$T_A"
  appel "Rôle respecté : l'entreprise n'a pas de profil étudiant (403)" 403 GET /utilisateurs/profils-etudiants/me/ "$T_ENT"
}

# ---------- 2. offres -------------------------------------------------------

offre_json() { echo "{\"titre\":\"$1\",\"description\":\"$2\",\"domaine\":\"$3\",\"ville\":\"$4\",\"duree_mois\":$5,\"competences_requises\":\"$6\",\"date_limite\":\"$(jours 60)\"}"; }

test_offres() {
  section "2. OFFRES : publier, rechercher, modifier, clôturer, supprimer (offres)"
  appel "Étudiant : publier une offre interdit" 403 POST /offres/offres/ "$T_A" "${JSON[@]}" -d "$(offre_json X x Y Z 3 q)"
  appel "Entreprise : publier l'offre 1" 201 POST /offres/offres/ "$T_ENT" "${JSON[@]}" -d "$(offre_json "Stage Développeur Django $TS" "Développer des API REST" Informatique Antananarivo 3 "Python, Django")"
  OFFRE1=$(echo "$CORPS" | jget id)
  appel "Entreprise : publier l'offre 2" 201 POST /offres/offres/ "$T_ENT" "${JSON[@]}" -d "$(offre_json "Stage Réseaux $TS" "Administrer un réseau" Télécom Mahajanga 6 "Cisco, Linux")"
  OFFRE2=$(echo "$CORPS" | jget id)
  appel "Entreprise : date limite dans le passé refusée" 400 POST /offres/offres/ "$T_ENT" "${JSON[@]}" \
        -d "{\"titre\":\"Passé\",\"description\":\"x\",\"domaine\":\"x\",\"ville\":\"x\",\"duree_mois\":2,\"competences_requises\":\"x\",\"date_limite\":\"2020-01-01\"}"

  appel "Étudiant : liste des offres" 200 GET /offres/offres/ "$T_A"
  appel "Recherche par mot-clé  ?q=django" 200 GET "/offres/offres/?q=django" "$T_A"
  appel "Recherche multi-mots  ?q=cisco mahajanga" 200 GET "/offres/offres/?q=cisco%20mahajanga" "$T_A"
  appel "Filtre par ville" 200 GET "/offres/offres/?ville=mahajanga" "$T_A"
  appel "Filtre par domaine" 200 GET "/offres/offres/?domaine=télécom" "$T_A"
  appel "Filtre par compétences" 200 GET "/offres/offres/?competences_requises=cisco" "$T_A"
  appel "Filtre par durée (2 à 4 mois)" 200 GET "/offres/offres/?duree_min=2&duree_max=4" "$T_A"
  appel "Tri par durée décroissante" 200 GET "/offres/offres/?ordering=-duree_mois" "$T_A"
  appel "Détail d'une offre (avec infos de l'entreprise)" 200 GET "/offres/offres/$OFFRE1/" "$T_A"

  appel "Entreprise : mes offres (ouvertes et clôturées)" 200 GET /offres/offres/mes-offres/ "$T_ENT"
  appel "Étudiant : mes-offres interdit" 403 GET /offres/offres/mes-offres/ "$T_A"
  appel "Entreprise : modifier son offre" 200 PATCH "/offres/offres/$OFFRE1/" "$T_ENT" "${JSON[@]}" -d '{"ville":"Antananarivo Centre"}'
  appel "Étudiant : modifier une offre interdit" 403 PATCH "/offres/offres/$OFFRE1/" "$T_A" "${JSON[@]}" -d '{"ville":"x"}'
  appel "Entreprise : clôturer l'offre 1" 200 POST "/offres/offres/$OFFRE1/cloturer/" "$T_ENT"
  appel "Étudiant : l'offre clôturée n'est plus visible (404)" 404 GET "/offres/offres/$OFFRE1/" "$T_A"
  appel "Entreprise : rouvrir l'offre 1" 200 POST "/offres/offres/$OFFRE1/reouvrir/" "$T_ENT"
  appel "Entreprise : créer une offre temporaire" 201 POST /offres/offres/ "$T_ENT" "${JSON[@]}" -d "$(offre_json Temporaire x x x 1 x)"
  local tmp; tmp=$(echo "$CORPS" | jget id)
  appel "Entreprise : supprimer une offre sans candidature" 204 DELETE "/offres/offres/$tmp/" "$T_ENT"
}

# ---------- 3. candidatures --------------------------------------------------

test_candidatures() {
  section "3. CANDIDATURES : postuler, suivre, décider, évaluer (candidatures)"
  appel "Étudiant A : lettre obligatoire" 400 POST /candidatures/mes-candidatures/ "$T_A" -F "offre=$OFFRE1"
  appel "Étudiant A : lettre non PDF refusée" 400 POST /candidatures/mes-candidatures/ "$T_A" -F "offre=$OFFRE1" -F "lettre_motivation=@$TMP/faux.txt;type=application/pdf"
  appel "Étudiant A : postuler à l'offre 1 (CV du profil utilisé)" 201 POST /candidatures/mes-candidatures/ "$T_A" -F "offre=$OFFRE1" -F "message=Bonjour" -F "lettre_motivation=@$TMP/lettre.pdf;type=application/pdf"
  CAND_A=$(echo "$CORPS" | jget id)
  appel "Étudiant A : double candidature refusée" 400 POST /candidatures/mes-candidatures/ "$T_A" -F "offre=$OFFRE1" -F "lettre_motivation=@$TMP/lettre.pdf;type=application/pdf"
  appel "Étudiant B : postuler avec un CV joint" 201 POST /candidatures/mes-candidatures/ "$T_B" -F "offre=$OFFRE1" -F "cv=@$TMP/cv.pdf;type=application/pdf" -F "lettre_motivation=@$TMP/lettre.pdf;type=application/pdf"
  CAND_B=$(echo "$CORPS" | jget id)

  appel "Étudiant A : suivre ses candidatures" 200 GET /candidatures/mes-candidatures/ "$T_A"
  appel "Étudiant A : filtrer par statut (historique)" 200 GET "/candidatures/mes-candidatures/?statut=EN_ATTENTE" "$T_A"
  appel "Étudiant B ne voit pas la candidature de A (404)" 404 GET "/candidatures/mes-candidatures/$CAND_A/" "$T_B"
  telecharger "Étudiant A : télécharger son propre CV" 200 "/candidatures/mes-candidatures/$CAND_A/cv/" "$T_A" candidature_cv.pdf
  telecharger "Étudiant B ne peut pas télécharger le CV de A (404)" 404 "/candidatures/mes-candidatures/$CAND_A/cv/" "$T_B" interdit.pdf

  appel "Entreprise : candidatures reçues pour l'offre 1" 200 GET "/candidatures/recues/?offre=$OFFRE1" "$T_ENT"
  appel "Entreprise : détail d'une candidature (profil, CV, lettre)" 200 GET "/candidatures/recues/$CAND_A/" "$T_ENT"
  telecharger "Entreprise : télécharger la lettre de motivation" 200 "/candidatures/recues/$CAND_A/lettre/" "$T_ENT" candidature_lettre.pdf
  appel "Étudiant : l'espace entreprise lui est interdit (403)" 403 GET /candidatures/recues/ "$T_A"
  appel "Entreprise : date de début dans le passé refusée" 400 POST "/candidatures/recues/$CAND_A/accepter/" "$T_ENT" "${JSON[@]}" -d '{"date_debut":"2020-01-06"}'
  appel "Entreprise : ACCEPTER la candidature de A (convention créée automatiquement)" 200 POST "/candidatures/recues/$CAND_A/accepter/" "$T_ENT" "${JSON[@]}" \
        -d "{\"commentaire\":\"Bienvenue dans notre équipe\",\"date_debut\":\"$(jours 30)\"}"
  appel "Entreprise : REFUSER la candidature de B (avec motif)" 200 POST "/candidatures/recues/$CAND_B/refuser/" "$T_ENT" "${JSON[@]}" -d '{"commentaire":"Profil non adapté"}'
  appel "Entreprise : décision déjà prise (409)" 409 POST "/candidatures/recues/$CAND_A/refuser/" "$T_ENT"
  appel "Étudiant A voit « Acceptée » + commentaire" 200 GET "/candidatures/mes-candidatures/$CAND_A/" "$T_A"
  appel "Étudiant B voit « Refusée » + motif" 200 GET "/candidatures/mes-candidatures/$CAND_B/" "$T_B"

  appel "Évaluation du stagiaire A : créer" 201 POST "/candidatures/recues/$CAND_A/evaluation/" "$T_ENT" "${JSON[@]}" \
        -d '{"note_technique":16,"note_autonomie":14,"note_communication":15,"note_assiduite":18,"appreciation":"Très bon stagiaire","recommande":true}'
  appel "Évaluation : note supérieure à 20 refusée" 400 POST "/candidatures/recues/$CAND_B/evaluation/" "$T_ENT" "${JSON[@]}" -d '{"note_technique":25,"note_autonomie":1,"note_communication":1,"note_assiduite":1}'
  appel "Évaluation d'un candidat refusé impossible" 400 POST "/candidatures/recues/$CAND_B/evaluation/" "$T_ENT" "${JSON[@]}" -d '{"note_technique":10,"note_autonomie":10,"note_communication":10,"note_assiduite":10}'
  appel "Évaluation : lire" 200 GET "/candidatures/recues/$CAND_A/evaluation/" "$T_ENT"
  appel "Évaluation : modifier une note" 200 PATCH "/candidatures/recues/$CAND_A/evaluation/" "$T_ENT" "${JSON[@]}" -d '{"note_technique":19}'
  appel "Évaluation : invisible pour l'étudiant (403)" 403 GET "/candidatures/recues/$CAND_A/evaluation/" "$T_A"

  appel "Étudiant A : postuler à l'offre 2" 201 POST /candidatures/mes-candidatures/ "$T_A" -F "offre=$OFFRE2" -F "lettre_motivation=@$TMP/lettre.pdf;type=application/pdf"
  local c2; c2=$(echo "$CORPS" | jget id)
  appel "Étudiant A : retirer une candidature en attente" 204 DELETE "/candidatures/mes-candidatures/$c2/" "$T_A"
  appel "Étudiant A : retirer une candidature acceptée refusé" 400 DELETE "/candidatures/mes-candidatures/$CAND_A/" "$T_A"
  appel "Entreprise : supprimer une offre qui a des candidatures refusé (409)" 409 DELETE "/offres/offres/$OFFRE1/" "$T_ENT"
  appel "Entreprise : supprimer l'offre 2 (plus aucune candidature)" 204 DELETE "/offres/offres/$OFFRE2/" "$T_ENT"
}

# ---------- 4. conventions ---------------------------------------------------

test_conventions() {
  section "4. CONVENTIONS : génération automatique, circuit de validation, attestation (conventions)"
  appel "Admin : conventions à traiter (brouillons)" 200 GET "/conventions/?statut=BROUILLON" "$T_ADM"
  CONV=$(echo "$CORPS" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for c in d.get('results', []):
    if str(c['candidature']) == '$CAND_A': print(c['id']); break")
  if [ -z "$CONV" ]; then echo "  ${ROUGE}✘ aucune convention créée automatiquement pour la candidature acceptée${FIN}"; KO=$((KO+1)); return; fi
  echo "  → convention n° $CONV créée automatiquement à l'acceptation"
  appel "Étudiant : le brouillon est invisible" 200 GET /conventions/ "$T_A"
  telecharger "Admin : télécharger le PDF brouillon (filigrane PROJET)" 200 "/conventions/$CONV/telecharger/" "$T_ADM" convention_brouillon.pdf
  telecharger "Étudiant : ne télécharge pas un brouillon (404)" 404 "/conventions/$CONV/telecharger/" "$T_A" interdit2.pdf
  appel "Étudiant : actions d'administration interdites (403)" 403 POST "/conventions/$CONV/valider/" "$T_A"
  appel "Admin : valider un brouillon refusé (409)" 409 POST "/conventions/$CONV/valider/" "$T_ADM"
  appel "Admin : corriger le lieu (le PDF est régénéré)" 200 PATCH "/conventions/$CONV/" "$T_ADM" "${JSON[@]}" -d '{"lieu":"Antananarivo - Siège"}'
  appel "Admin : dates incohérentes refusées" 400 PATCH "/conventions/$CONV/" "$T_ADM" "${JSON[@]}" -d '{"date_fin":"2020-01-01"}'
  appel "Admin : SOUMETTRE (brouillon -> en attente)" 200 POST "/conventions/$CONV/soumettre/" "$T_ADM"
  appel "Admin : rejeter sans motif refusé" 400 POST "/conventions/$CONV/rejeter/" "$T_ADM" "${JSON[@]}" -d '{}'
  appel "Admin : REJETER avec motif (retour en brouillon)" 200 POST "/conventions/$CONV/rejeter/" "$T_ADM" "${JSON[@]}" -d '{"motif":"Dates à confirmer"}'
  appel "Admin : soumettre à nouveau" 200 POST "/conventions/$CONV/soumettre/" "$T_ADM"
  appel "Étudiant : voit la convention en attente" 200 GET /conventions/ "$T_A"
  appel "Étudiant : téléchargement refusé tant que non validée (409)" 409 GET "/conventions/$CONV/telecharger/" "$T_A"
  appel "Admin : VALIDER (notifie l'étudiant et l'entreprise)" 200 POST "/conventions/$CONV/valider/" "$T_ADM"
  telecharger "Étudiant : télécharger sa convention validée" 200 "/conventions/$CONV/telecharger/" "$T_A" convention_validee.pdf
  telecharger "Entreprise : télécharger la convention" 200 "/conventions/$CONV/telecharger/" "$T_ENT" convention_validee_entreprise.pdf
  telecharger "Autre étudiant : accès refusé (404)" 404 "/conventions/$CONV/telecharger/" "$T_B" interdit3.pdf
  appel "Admin : modifier après validation refusé (409)" 409 PATCH "/conventions/$CONV/" "$T_ADM" "${JSON[@]}" -d '{"lieu":"x"}'
  appel "Admin : scan non PDF refusé" 400 POST "/conventions/$CONV/signer/" "$T_ADM" -F "fichier_signe=@$TMP/faux.txt;type=application/pdf"
  appel "Admin : SIGNER avec le scan signé" 200 POST "/conventions/$CONV/signer/" "$T_ADM" -F "fichier_signe=@$TMP/scan.pdf;type=application/pdf"
  telecharger "Étudiant : télécharge maintenant le scan signé" 200 "/conventions/$CONV/telecharger/" "$T_A" convention_signee.pdf

  appel "Attestation : stage pas terminé (409)" 409 POST "/conventions/$CONV/emettre-attestation/" "$T_ENT"
  echo "  (simulation : on recule les dates du stage pour qu'il soit terminé)"
  $PY shell -c "from conventions.models import Convention; import datetime as d; t=d.date.today(); Convention.objects.filter(pk=$CONV).update(date_debut=t-d.timedelta(days=100), date_fin=t-d.timedelta(days=10))" >/dev/null 2>&1
  appel "Étudiant : l'émission lui est interdite (403)" 403 POST "/conventions/$CONV/emettre-attestation/" "$T_A"
  appel "Entreprise : ÉMETTRE l'attestation de stage" 200 POST "/conventions/$CONV/emettre-attestation/" "$T_ENT"
  telecharger "Étudiant : télécharger son attestation" 200 "/conventions/$CONV/attestation/" "$T_A" attestation.pdf
  appel "Attestation déjà émise (409)" 409 POST "/conventions/$CONV/emettre-attestation/" "$T_ENT"
}

# ---------- 5. administration ------------------------------------------------

test_administration() {
  section "5. ADMINISTRATION : tableau de bord, statistiques, utilisateurs, audit (administration)"
  appel "Étudiant : tableau de bord interdit (403)" 403 GET /admin/tableau-de-bord/ "$T_A"
  appel "Admin : TABLEAU DE BORD (stages en cours, conventions à traiter...)" 200 GET /admin/tableau-de-bord/ "$T_ADM"
  appel "Admin : STATISTIQUES (taux d'acceptation, temps moyens, par entreprise et par domaine)" 200 GET /admin/statistiques/ "$T_ADM"
  appel "Admin : liste des utilisateurs" 200 GET /admin/utilisateurs/ "$T_ADM"
  appel "Admin : filtrer les entreprises" 200 GET "/admin/utilisateurs/?role=ENTREPRISE" "$T_ADM"
  appel "Admin : rechercher un utilisateur" 200 GET "/admin/utilisateurs/?search=$ETU_B" "$T_ADM"
  appel "Étudiant : ne peut pas désactiver un compte (403)" 403 POST "/admin/utilisateurs/$ID_T_B/desactiver/" "$T_A"
  appel "Admin : ne peut pas désactiver son propre compte (400)" 400 POST "/admin/utilisateurs/$ID_ADM/desactiver/" "$T_ADM"
  appel "Admin : DÉSACTIVER le compte de l'étudiant B" 200 POST "/admin/utilisateurs/$ID_T_B/desactiver/" "$T_ADM"
  appel "Compte désactivé : connexion refusée" 401 POST /auth/login/ "" "${JSON[@]}" -d "{\"username\":\"$ETU_B\",\"password\":\"$MDP\"}"
  appel "Compte désactivé : son token existant ne fonctionne plus" 401 GET /auth/me/ "$T_B"
  appel "Admin : ACTIVER le compte de l'étudiant B" 200 POST "/admin/utilisateurs/$ID_T_B/activer/" "$T_ADM"
  appel "Admin : journal d'audit" 200 GET "/admin/journal/?page_size=100" "$T_ADM"
  appel "Admin : journal filtré (validations de conventions)" 200 GET "/admin/journal/?action=CONVENTION_VALIDEE" "$T_ADM"
  appel "Journal en lecture seule (écriture refusée)" 405 POST /admin/journal/ "$T_ADM" "${JSON[@]}" -d '{}'
  telecharger "Admin : rapport CSV des candidatures (ouvrable dans Excel)" 200 /admin/rapports/candidatures.csv "$T_ADM" rapport_candidatures.csv csv
  [ -f "$RES/rapport_candidatures.csv" ] && echo "  premières lignes : $(head -c 200 "$RES/rapport_candidatures.csv" | tr '\n' ' ')"
}

# ---------- 6. notifications -------------------------------------------------

test_notifications() {
  section "6. NOTIFICATIONS dans l'interface (notifications)"
  appel "Badge : nombre de notifications non lues (étudiant A)" 200 GET /notifications/non-lues/ "$T_A"
  appel "Liste des notifications non lues" 200 GET "/notifications/?lue=false" "$T_A"
  local nid; nid=$(echo "$CORPS" | jget results.0.id)
  [ -n "$nid" ] && appel "Marquer la première comme lue" 200 POST "/notifications/$nid/lire/" "$T_A"
  [ -n "$nid" ] && appel "L'étudiant B ne peut pas lire la notification de A (404)" 404 POST "/notifications/$nid/lire/" "$T_B"
  appel "Tout marquer comme lu" 200 POST /notifications/tout-lire/ "$T_A"
  appel "Badge après lecture : 0" 200 GET /notifications/non-lues/ "$T_A"
  appel "Entreprise : ses notifications (candidatures reçues)" 200 GET /notifications/ "$T_ENT"
  appel "Admin : ses notifications (conventions à traiter)" 200 GET /notifications/ "$T_ADM"
}

bilan() {
  echo; echo "${BLEU}============================================================${FIN}"
  echo "  Résultat : ${VERT}$OK réussis${FIN}, ${ROUGE}$KO échecs${FIN}"
  echo "  Fichiers générés : $RES/"
  echo "${BLEU}============================================================${FIN}"
  [ "$KO" -eq 0 ]
}

# ---------- exécution --------------------------------------------------------

cible="${1:-notifications}"
preparation
for s in auth offres candidatures conventions administration notifications; do
  "test_$s"
  [ "$s" = "$cible" ] && break
done
bilan
