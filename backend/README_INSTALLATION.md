# Mise à jour : conventions automatiques, notifications, administration

Testé avec Django 6.1 / DRF 3.18 : 136 vérifications de bout en bout (nouveaux modules)
+ 114 vérifications de non-régression (authentification, espaces étudiant et entreprise).

## 1. Dépendance
    pip install reportlab
et ajouter `reportlab` à `requirements.txt` (bibliothèque 100 % Python : aucune installation système,
elle fonctionne donc telle quelle sur Render).

## 2. Copier les fichiers
Dézipper à la racine du projet (à côté de `manage.py`) et accepter le remplacement.
- Nouveau : dossier `administration/` (tableau de bord, utilisateurs, journal d'audit, rapports)
- Remplacés : `config/urls.py`, `utilisateurs/permissions.py`,
  `candidatures/{apps,signals,serializers,views,admin}.py`,
  `conventions/*` (+ commande `generer_conventions`), `notifications/*` (+ modèles d'e-mails)

## 3. config/settings.py
Dans `INSTALLED_APPS`, ajouter `'administration',` (les autres apps y sont déjà).
À la fin du fichier :

    # --- Convention / attestation PDF ---
    UNIVERSITE_NOM = config('UNIVERSITE_NOM', default='Université')
    UNIVERSITE_ADRESSE = config('UNIVERSITE_ADRESSE', default='')
    UNIVERSITE_VILLE = config('UNIVERSITE_VILLE', default='')

Dans `.env` (adapter) :

    UNIVERSITE_NOM=Université de ...
    UNIVERSITE_ADRESSE=...
    UNIVERSITE_VILLE=Antananarivo

## 4. Migrations
    python manage.py makemigrations administration notifications conventions
    python manage.py migrate

## 5. Candidatures déjà acceptées (une seule fois)
    python manage.py generer_conventions

## 6. Modifier le texte de la convention
Les clauses sont dans `conventions/pdf.py` (TEMPLATE_PARTIES et TEMPLATE_ARTICLES).
Les {champs} sont remplis automatiquement. Faire relire ce texte par l'université avant usage réel.
