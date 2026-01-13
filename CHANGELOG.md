# Changelog

Toutes les modifications notables de ce projet seront documentées dans ce fichier.

## [1.0.0] - 2026-01-13

### 🎉 Version initiale

#### Ajouté
- Système de gestion de parties de Skyjo et Skyjo Action
- Suivi des scores par manche avec affichage matriciel
- Système d'authentification à deux niveaux (codes 1666 et 1664)
- Statistiques détaillées par type de jeu
- Export des données vers Excel/OneDrive
- Interface Metro UI responsive (mobile + desktop)
- Consultation des règles du jeu (PDF intégré)
- Recherche de parties par date
- Bouton retour avec navigation historique
- Système de commentaires sur les parties
- Détection automatique de fin de partie (score ≥ 100)

#### Fonctionnalités par niveau d'accès

**Accès Interne (1666)**
- Création et consultation de toutes les parties
- Accès complet aux statistiques
- Export vers Excel/OneDrive
- Gestion des règles du jeu

**Accès Externe (1664)**
- Création de parties (taguées 'ext')
- Consultation uniquement des parties 'ext'
- Pas d'accès aux statistiques
- Interface simplifiée

#### Design et UX
- Bannière Skyjo en haut de page (article-skyjo-bandeau-bis.webp)
- Fond dégradé arc-en-ciel harmonieux
- Tuiles Metro avec dégradés colorés :
  - Violet/Mauve pour "Nouvelle partie"
  - Cyan/Bleu pour "Stats"
  - Vert/Cyan pour "Rechercher"
- Interface responsive optimisée mobile et desktop
- Logo agrandi de 30% sur mobile pour meilleure visibilité
- Bouton retour en bas à droite de chaque page
- Système de notifications (flash messages)

#### Technique
- Flask 3.0 comme framework web
- SQLite comme base de données
- Gunicorn comme serveur WSGI
- Apache comme reverse proxy
- Support SSL via Let's Encrypt
- Gestion des sessions Flask pour l'authentification
- Filtrage SQL dynamique selon le niveau d'accès
- Migration automatique du schéma de base de données

#### Sécurité
- Protection par code d'accès en session
- Séparation stricte des données par access_type
- Headers de sécurité (X-Frame-Options, X-Content-Type-Options)
- Fichiers sensibles exclus du dépôt Git
- Permissions fichiers strictes en production

---

## Historique des développements (pré-release)

### Phase 5 : Design et finitions (12-13 janvier 2026)
- Ajout du système d'authentification à deux niveaux
- Harmonisation du design avec fond dégradé
- Optimisation de l'affichage du logo (mobile et desktop)
- Préparation pour mise en production

### Phase 4 : UX et responsive (12 janvier 2026)
- Harmonisation des couleurs des tuiles Metro
- Optimisation mobile (débordement champs date)
- Déplacement du titre "Parties en cours" sous la recherche
- Amélioration du bouton rechercher avec gradient
- Ajout du bouton de déconnexion

### Phase 3 : Statistiques avancées (12 janvier 2026)
- Implémentation du système de statistiques par type de jeu
- Menu de sélection par type de jeu
- Podium des 3 meilleurs joueurs
- Statistiques détaillées (moyenne, médiane, meilleur, pire)
- "Boss des coups de bol" et "Looser du pire"
- Tuiles Metro avec icônes et compteurs

### Phase 2 : Règles et navigation (12 janvier 2026)
- Ajout du système de consultation des règles PDF
- Table `game_rules` pour gérer les PDFs par type de jeu
- Bouton d'accès aux règles depuis la page de partie
- Bouton retour avec `history.back()` sur toutes les pages
- Amélioration de la navigation

### Phase 1 : Fonctionnalités de base (11-12 janvier 2026)
- Création du système de gestion de parties
- Interface de saisie des scores par manche
- Tableau d'affichage des scores et totaux
- Système de commentaires
- Recherche par date
- Export Excel/OneDrive
- Design Metro UI initial

---

## Notes de version

### Migrations nécessaires

Si vous mettez à jour depuis une version antérieure, les migrations SQL suivantes sont appliquées automatiquement au démarrage :

```sql
-- Ajout de created_at aux rounds (si absent)
ALTER TABLE rounds ADD COLUMN created_at TEXT;

-- Ajout de access_type aux games (si absent)
ALTER TABLE games ADD COLUMN access_type TEXT DEFAULT 'int';
```

### Compatibilité

- Python 3.10 minimum requis
- Testé sur Ubuntu 22.04/24.04
- Compatible Apache 2.4+
- Navigateurs supportés : Chrome 90+, Firefox 88+, Safari 14+, Edge 90+

### Changements cassants

Aucun pour cette version initiale.

---

**Légende des versions**
- 🎉 Version majeure
- ✨ Nouvelle fonctionnalité
- 🐛 Correction de bug
- 🔒 Sécurité
- 📝 Documentation
- 🚀 Performance
