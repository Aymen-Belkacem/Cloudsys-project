# Comtrade Anomalies – Étape 2 : application Streamlit

Version placeholder : l'app affiche un *status report* (version, environnement,
tâche ECS, état des composants) sans se connecter à une base de données.
Objectif : valider la chaîne **Docker → Amazon ECR → Amazon ECS Express Mode**.

## Arborescence

```
comtrade-app/
├── app/
│   ├── app.py                 # application Streamlit (status report)
│   ├── requirements.txt
│   └── .streamlit/config.toml # port 8501, écoute sur 0.0.0.0
├── Dockerfile                 # image poussée sur ECR
├── .dockerignore
├── docker-compose.yml         # développement local uniquement
└── infra/
    ├── config.env             # noms des ressources, région, CPU/mémoire
    ├── deploy.sh              # crée / met à jour toutes les ressources AWS
    └── teardown.sh            # supprime les ressources (arrête la facturation)
```

## 1. Tester en local

```bash
docker compose up --build
# puis ouvrir http://localhost:8501
```

Le code est monté dans le conteneur : une modification de `app/app.py`
recharge la page sans rebuild.

## 2. Déployer sur AWS (depuis WSL)

```bash
chmod +x infra/*.sh        # une seule fois
./infra/deploy.sh
```

Le script crée, dans l'ordre : le dépôt ECR, l'image (build + push), les rôles
IAM (exécution + infrastructure), le log group CloudWatch, le cluster ECS et le
service ECS Express Mode. Il attend que le service soit stable puis affiche l'URL
publique (`https://<service>.ecs.<region>.on.aws`).

Relancer `./infra/deploy.sh` après une modification du code : il pousse une
nouvelle image (tag unique) et met à jour le service sans interruption.

La région vient de `aws configure` (sinon `eu-central-1`). Pour en forcer une :
`AWS_REGION=eu-west-3 ./infra/deploy.sh`.

## 3. Vérifier

- La page affiche « Plateforme : AWS ECS (Fargate) » et le bloc « Tâche ECS ».
- Le bouton du bloc « Test interactif » incrémente le compteur : les WebSockets
  passent bien par l'ALB.
- Logs : `aws logs tail /ecs/comtrade-app --follow`

## 4. Tout supprimer

```bash
./infra/teardown.sh               # service + ALB, cluster, ECR, logs
./infra/teardown.sh --delete-iam  # idem + rôles IAM
```

> ⚠️ Tant que le service existe, l'ALB et la tâche Fargate sont facturés,
> même sans trafic. Lancez `teardown.sh` à la fin de chaque session de travail.

## Pré-requis

- AWS CLI v2 récente (doit connaître `aws ecs create-express-gateway-service`)
- Docker Desktop avec l'intégration WSL activée
- Un VPC par défaut dans la région (sinon renseigner `SUBNETS` dans `config.env`)

## Étapes suivantes

- Connexion DocumentDB : renseigner `SUBNETS` / `SECURITY_GROUPS` (VPC du cluster),
  passer l'URI en secret (Secrets Manager), ajouter le certificat CA au Dockerfile.
- Appel à la Lambda IA (étape 3) : ajouter un rôle de tâche (`--task-role-arn`)
  avec `lambda:InvokeFunction`.
