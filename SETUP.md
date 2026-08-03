# Setup Jour 1-2 — infrastructure de base

Ce guide couvre uniquement la mise en place de l'infrastructure (Postgres, MinIO, Airflow, MLflow),
avant d'attaquer le simulateur de donnees (jour 3-4).

---

## 0. Avant de lancer quoi que ce soit — gerer les anciens projets Docker

Comme Docker Desktop contient deja des images/containers d'anciens projets, voici comment eviter
tout conflit sans toucher a l'existant.

### Verifier ce qui tourne deja

```powershell
docker ps -a
docker images
docker volume ls
docker network ls
```

### Pourquoi ce projet ne rentrera pas en conflit

- `COMPOSE_PROJECT_NAME=wfm` dans le `.env` : tous les objets Docker crees (containers, volumes,
  reseau) sont prefixes `wfm_` et totalement isoles des autres projets. Un `docker compose down -v`
  lance depuis ce dossier ne touchera **jamais** aux volumes d'un autre projet.
- Les volumes sont nommes explicitement (`wfm_pg_data`, `wfm_minio_data`) plutot que laisses en
  volumes anonymes, pour que tu puisses les identifier facilement dans `docker volume ls`.
- Les ports exposes sont volontairement non-standards (`5433` au lieu de `5432` pour Postgres,
  `8081` au lieu de `8080` pour Airflow) pour eviter un conflit si un autre projet utilise deja les
  ports par defaut. Si un port est quand meme deja pris, modifie juste la valeur correspondante
  dans `.env` (aucun autre fichier a toucher).

### Verifier qu'un port est libre avant de lancer (PowerShell)

```powershell
Get-NetTCPConnection -LocalPort 5433 -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort 8081 -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort 5001 -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort 9000,9001 -ErrorAction SilentlyContinue
```
Si une commande renvoie un resultat, le port est deja utilise -> change la valeur dans `.env`.

### Nettoyer sans risque (optionnel, si Docker Desktop est charge)

```powershell
docker system df          # voir l'espace disque utilise par Docker
docker container prune     # supprime uniquement les containers ARRETES (aucun risque)
docker image prune         # supprime uniquement les images "dangling" (non taguees, orphelines)
```
Ne lance surtout pas `docker system prune -a --volumes` sans verifier : ca supprimerait aussi les
images/volumes d'autres projets que tu utilises peut-etre encore.

---

## 1. Installation des fichiers

1. Extrais l'archive fournie directement dans `C:\Users\Ahmed\Desktop\WFM`
2. Verifie que tu as bien cette structure a la racine :

```
WFM/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
├── SETUP.md
├── docker/
├── init-scripts/
├── airflow/
├── data/
├── ml/
├── spark_jobs/
├── api/
├── monitoring/
├── frontend/
└── tests/
```

3. Copie `.env.example` en `.env` :

```powershell
Copy-Item .env.example .env
```

4. Ouvre `.env` et change au minimum `POSTGRES_PASSWORD` et `MINIO_ROOT_PASSWORD` (n'importe quelle
   valeur, c'est du local, mais evite de laisser "change_me_locally").

---

## 2. Generer une cle Fernet pour Airflow (optionnel mais recommande)

Airflow chiffre certaines donnees sensibles (connexions, variables) avec une cle Fernet. Si tu la
laisses vide, Airflow en genere une automatiquement au demarrage (ca marche, mais elle change a
chaque rebuild, ce qui invalide les connexions enregistrees). Pour une cle stable :

```powershell
docker run --rm python:3.11-slim sh -c "pip install cryptography -q && python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
```

Copie la valeur generee dans `AIRFLOW_FERNET_KEY=` du fichier `.env`.

---

## 3. Lancer l'infrastructure

Depuis le dossier `WFM/` :

```powershell
docker compose up -d --build
```

Le premier build peut prendre 3-5 minutes (telechargement des images Airflow/Postgres/MinIO + build
des images custom). Les fois suivantes seront quasi instantanees.

### Suivre le demarrage

```powershell
docker compose ps
docker compose logs -f airflow-init
```

Attends de voir le message de creation de l'utilisateur admin dans les logs de `airflow-init`
avant de considerer que c'est bon (le service `airflow-init` doit finir avec le statut "exited (0)").

---

## 4. Verifier que tout fonctionne

| Service | URL | Identifiants |
|---|---|---|
| Airflow | http://localhost:8081 | admin / admin (ou ceux definis dans `.env`) |
| MLflow | http://localhost:5001 | aucun (pas d'auth en local) |
| MinIO console | http://localhost:9001 | minio_admin / (ton mot de passe `.env`) |
| Postgres | localhost:5433 | via un client SQL (DBeaver, pgAdmin) si besoin |

Dans MinIO, verifie que deux buckets existent deja : `mlflow-artifacts` et `wfm-datalake`
(crees automatiquement par le service `minio-init`).

Dans MLflow, l'interface doit se charger sans erreur (meme si aucune experience n'existe encore).

Dans Airflow, connecte-toi et verifie que la liste des DAGs est vide (normal, on les ajoute jour 3+)
mais que l'interface repond sans erreur 500.

---

## 5. Commandes utiles au quotidien

```powershell
docker compose stop          # arrete les containers, garde les donnees
docker compose start         # redemarre sans tout reconstruire
docker compose down          # supprime les containers, garde les volumes (donnees)
docker compose down -v       # supprime aussi les volumes (repart de zero) - reserve aux tests
docker compose logs -f api   # suit les logs d'un service en particulier
```

---

## 6. Ce qui reste a faire (jour 3-4, prochaine etape)

- Simulateur de donnees (`data/simulator/`) generant les evenements d'appels + referentiel agents
- Premier DAG Airflow (`airflow/dags/dag_ingestion.py`) qui depose les fichiers simules dans MinIO
  et les charge dans la base `wfm_app` de Postgres

Rien a faire cote infra a ce stade — cette base est reutilisee telle quelle jusqu'a la fin du projet.
