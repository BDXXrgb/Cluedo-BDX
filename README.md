\# BDX Cluedo en Ligne



Jeu multijoueur en ligne inspiré de Cluedo.



\## Fonctions

\- Authentification JWT

\- SQLite par défaut

\- PostgreSQL possible via DATABASE\_URL

\- WebSocket temps réel

\- Plateau visuel

\- Déplacement case par case

\- Passages secrets

\- Chat

\- Suggestions et accusations

\- Historique sauvegardé

\- Classement global

\- Bots avancés



\## Installation

```bash

pip install -r requirements.txt

cp .env.example .env

uvicorn app.main:app --reload

```



\## Lancement

Ouvre http://127.0.0.1:8000



\## Base de données

Par défaut SQLite.

Pour PostgreSQL, change DATABASE\_URL dans `.env`.

