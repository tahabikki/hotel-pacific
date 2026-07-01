# 🏨 Hôtel pacific — Gestion des Factures

Application Django pour générer et gérer des factures d'hôtel avec base de données SQLite et export PDF.

## 📋 Fonctionnalités

- ✅ Création, édition, suppression de factures
- ✅ Liste des factures avec recherche et tri
- ✅ Gestion clients (carnet d'adresses)
- ✅ Calcul automatique : TVA 10% + taxe séjour 2%
- ✅ Export PDF identique au modèle original (ReportLab)
- ✅ Statuts : Provisoire / Définitive / Acquittée
- ✅ Interface admin Django pour gestion avancée
- ✅ Numérotation automatique des réservations

## 🚀 Installation

### Prérequis
- Python 3.10+ (testé sur 3.11)
- Mac M1 / Linux / Windows

### Étapes

```bash
# 1. Aller dans le dossier du projet
cd hotel_pacific

# 2. Créer un environnement virtuel
python3 -m venv venv

# 3. L'activer
source venv/bin/activate          # Mac/Linux
# venv\Scripts\activate           # Windows

# 4. Installer les dépendances
source venv/bin/activate 

# 5. Créer la base de données (SQLite)
python manage.py migrate

# 6. Créer un superuser (admin)
python manage.py createsuperuser
# Choisis un username, email, mot de passe

# 7. (Optionnel) Charger des données de démo
python manage.py loaddata factures/fixtures/demo.json

# 8. Lancer le serveur
python manage.py runserver
```

L'app est maintenant accessible sur :
- **App** : http://127.0.0.1:8000/
- **Admin** : http://127.0.0.1:8000/admin/

## 📂 Structure

```
hotel_pacific/
├── hotel_pacific/          # Config projet Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── factures/               # App principale
│   ├── models.py           # Client, Facture, LigneFacture
│   ├── views.py            # Vues CRUD + génération PDF
│   ├── forms.py            # Formulaires Django
│   ├── urls.py
│   ├── admin.py
│   └── pdf_generator.py    # Génération PDF ReportLab
├── templates/factures/     # Templates HTML
├── static/                 # CSS, JS
├── manage.py
├── requirements.txt
└── README.md
```

## 🔧 Configuration

Les paramètres de l'hôtel (nom, adresse, SIRET, TVA par défaut) sont dans :
`factures/models.py` → classe `ParametresHotel`

Pour les modifier : interface admin Django, ou directement en code.

## 💡 Utilisation rapide

1. Va sur http://127.0.0.1:8000/
2. Clique "Nouvelle facture"
3. Remplis les champs (numéro réservation suggéré automatiquement)
4. Enregistre → tu peux ensuite générer le PDF, modifier, ou marquer comme acquittée

## ⚠️ Production

Pour déployer en prod (au-delà du local) :
- Mettre `DEBUG = False` dans `settings.py`
- Configurer `ALLOWED_HOSTS`
- Remplacer SQLite par PostgreSQL si beaucoup de factures
- Utiliser gunicorn + nginx

Pour du local pur (1 utilisateur sur ta machine), la config par défaut suffit largement.
