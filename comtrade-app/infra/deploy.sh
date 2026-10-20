#!/usr/bin/env bash
# Deploie l'application Streamlit sur AWS :
#   1. depot Amazon ECR
#   2. build + push de l'image Docker
#   3. roles IAM (execution + infrastructure) requis par ECS Express Mode
#   4. log group CloudWatch
#   5. cluster ECS
#   6. service ECS Express Mode (cree au 1er lancement, mis a jour ensuite)
#   7. attente de stabilisation + affichage de l'URL publique
#
# Le script est relancable : chaque etape verifie si la ressource existe deja.
# Usage (depuis WSL, a la racine du projet ou ailleurs) : ./infra/deploy.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=infra/config.env
source "$SCRIPT_DIR/config.env"

export AWS_PAGER=""          # pas de pager "less" sur les sorties AWS CLI
export AWS_REGION

log()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
die()  { printf '\033[1;31mErreur : %s\033[0m\n' "$*" >&2; exit 1; }

# --------------------------------------------------------------------------- #
# 0. Pre-requis
# --------------------------------------------------------------------------- #
log "Verification des pre-requis"
command -v aws    >/dev/null || die "AWS CLI introuvable"
command -v docker >/dev/null || die "Docker introuvable"
docker info >/dev/null 2>&1  || die "Docker ne repond pas (Docker Desktop est-il lance, integration WSL activee ?)"
aws ecs create-express-gateway-service --generate-cli-skeleton >/dev/null 2>&1 \
  || die "Votre AWS CLI ne connait pas ECS Express Mode : mettez-la a jour (AWS CLI v2 recente)"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)" \
  || die "Identifiants AWS invalides (aws configure ?)"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
REPO_URI="${REGISTRY}/${ECR_REPO}"
info "Compte : $ACCOUNT_ID | Region : $AWS_REGION"

# Tag d'image : hash git court si dispo, sinon horodatage.
# Un tag unique par deploiement force ECS a lancer une nouvelle revision.
if git -C "$PROJECT_ROOT" rev-parse --short HEAD >/dev/null 2>&1; then
  IMAGE_TAG="$(git -C "$PROJECT_ROOT" rev-parse --short HEAD)-$(date +%H%M%S)"
else
  IMAGE_TAG="$(date +%Y%m%d-%H%M%S)"
fi
IMAGE_URI="${REPO_URI}:${IMAGE_TAG}"

# --------------------------------------------------------------------------- #
# 1. Depot ECR
# --------------------------------------------------------------------------- #
log "Depot ECR : $ECR_REPO"
if aws ecr describe-repositories --repository-names "$ECR_REPO" >/dev/null 2>&1; then
  info "Existe deja"
else
  aws ecr create-repository \
    --repository-name "$ECR_REPO" \
    --image-scanning-configuration scanOnPush=true \
    --query repository.repositoryUri --output text
fi

# --------------------------------------------------------------------------- #
# 2. Build + push de l'image
# --------------------------------------------------------------------------- #
log "Connexion Docker a ECR"
aws ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY"

log "Build de l'image : $IMAGE_URI"
# linux/amd64 = architecture X86_64 utilisee par le service Fargate
docker build \
  --platform linux/amd64 \
  --build-arg APP_VERSION="$IMAGE_TAG" \
  -t "$IMAGE_URI" \
  "$PROJECT_ROOT"

log "Push de l'image vers ECR"
docker push "$IMAGE_URI"

# --------------------------------------------------------------------------- #
# 3. Roles IAM
# --------------------------------------------------------------------------- #
ROLES_CREATED=false

# ensure_role <nom> <service principal> <ARN policy managee>
ensure_role() {
  local name="$1" principal="$2" policy_arn="$3"
  if aws iam get-role --role-name "$name" >/dev/null 2>&1; then
    info "Role $name : existe deja"
  else
    aws iam create-role \
      --role-name "$name" \
      --assume-role-policy-document "{
        \"Version\": \"2012-10-17\",
        \"Statement\": [{
          \"Effect\": \"Allow\",
          \"Principal\": { \"Service\": \"$principal\" },
          \"Action\": \"sts:AssumeRole\"
        }]
      }" >/dev/null
    info "Role $name : cree"
    ROLES_CREATED=true
  fi
  # attach-role-policy est idempotent
  aws iam attach-role-policy --role-name "$name" --policy-arn "$policy_arn"
}

log "Roles IAM"
# Role d'execution : utilise par l'agent ECS pour tirer l'image ECR et ecrire les logs
ensure_role "$EXEC_ROLE_NAME" "ecs-tasks.amazonaws.com" \
  "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
# Role d'infrastructure : utilise par ECS pour creer ALB, target group, SG, autoscaling
ensure_role "$INFRA_ROLE_NAME" "ecs.amazonaws.com" \
  "arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices"

EXEC_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${EXEC_ROLE_NAME}"
INFRA_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${INFRA_ROLE_NAME}"

if [[ "$ROLES_CREATED" == true ]]; then
  info "Attente de la propagation IAM (15 s)..."
  sleep 15
fi

# --------------------------------------------------------------------------- #
# 4. Log group CloudWatch
# --------------------------------------------------------------------------- #
log "Log group CloudWatch : $LOG_GROUP"
existing_lg="$(aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" \
  --query "logGroups[?logGroupName=='${LOG_GROUP}'].logGroupName | [0]" --output text)"
if [[ "$existing_lg" == "$LOG_GROUP" ]]; then
  info "Existe deja"
else
  aws logs create-log-group --log-group-name "$LOG_GROUP"
  info "Cree"
fi
aws logs put-retention-policy --log-group-name "$LOG_GROUP" --retention-in-days "$LOG_RETENTION_DAYS"

# --------------------------------------------------------------------------- #
# 5. Cluster ECS
# --------------------------------------------------------------------------- #
log "Cluster ECS : $CLUSTER_NAME"
# create-cluster renvoie le cluster existant s'il est deja ACTIVE
aws ecs create-cluster --cluster-name "$CLUSTER_NAME" --query cluster.status --output text

# --------------------------------------------------------------------------- #
# 6. Service ECS Express Mode
# --------------------------------------------------------------------------- #
PRIMARY_CONTAINER=$(cat <<JSON
{
  "image": "${IMAGE_URI}",
  "containerPort": ${CONTAINER_PORT},
  "awsLogsConfiguration": { "logGroup": "${LOG_GROUP}", "logStreamPrefix": "ecs" },
  "environment": [
    { "name": "APP_ENV", "value": "aws" },
    { "name": "APP_VERSION", "value": "${IMAGE_TAG}" }
  ]
}
JSON
)
SCALING_TARGET="minTaskCount=${MIN_TASKS},maxTaskCount=${MAX_TASKS}"

NETWORK_ARGS=()
if [[ -n "$SUBNETS" ]]; then
  NETWORK_ARGS=(--network-configuration "subnets=${SUBNETS}${SECURITY_GROUPS:+,securityGroups=${SECURITY_GROUPS}}")
fi

service_status="$(aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" \
  --query 'services[0].status' --output text 2>/dev/null || true)"

if [[ "$service_status" == "ACTIVE" ]]; then
  log "Mise a jour du service Express : $SERVICE_NAME"
  SERVICE_ARN="$(aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" \
    --query 'services[0].serviceArn' --output text)"
  aws ecs update-express-gateway-service \
    --service-arn "$SERVICE_ARN" \
    --primary-container "$PRIMARY_CONTAINER" \
    --health-check-path "$HEALTH_CHECK_PATH" \
    --cpu "$TASK_CPU" \
    --memory "$TASK_MEMORY" \
    --scaling-target "$SCALING_TARGET" \
    "${NETWORK_ARGS[@]}" \
    --query 'service.status.statusCode' --output text
else
  log "Creation du service Express : $SERVICE_NAME"
  SERVICE_ARN="$(aws ecs create-express-gateway-service \
    --service-name "$SERVICE_NAME" \
    --cluster "$CLUSTER_NAME" \
    --execution-role-arn "$EXEC_ROLE_ARN" \
    --infrastructure-role-arn "$INFRA_ROLE_ARN" \
    --primary-container "$PRIMARY_CONTAINER" \
    --health-check-path "$HEALTH_CHECK_PATH" \
    --cpu "$TASK_CPU" \
    --memory "$TASK_MEMORY" \
    --cpu-architecture X86_64 \
    --scaling-target "$SCALING_TARGET" \
    "${NETWORK_ARGS[@]}" \
    --tags key=project,value="$PROJECT_NAME" \
    --query 'service.serviceArn' --output text)"
fi
info "Service : $SERVICE_ARN"

# --------------------------------------------------------------------------- #
# 7. Attente + URL
# --------------------------------------------------------------------------- #
log "Attente de la stabilisation du service (jusqu'a ~10 min la premiere fois)..."
if ! aws ecs wait services-stable --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME"; then
  info "Le service n'est pas encore stable. Diagnostic :"
  info "  aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --query 'services[0].events[:5]'"
  info "  aws logs tail $LOG_GROUP --since 15m"
  exit 1
fi

ENDPOINT="$(aws ecs describe-express-gateway-service --service-arn "$SERVICE_ARN" \
  --query "service.activeConfigurations[0].ingressPaths[?accessType=='PUBLIC'].endpoint | [0]" \
  --output text 2>/dev/null || true)"

log "Deploiement termine"
info "Image   : $IMAGE_URI"
if [[ -n "$ENDPOINT" && "$ENDPOINT" != "None" ]]; then
  [[ "$ENDPOINT" == http* ]] || ENDPOINT="https://${ENDPOINT}"
  info "URL     : $ENDPOINT"
  info "(le DNS peut mettre quelques minutes a repondre lors de la premiere creation)"
else
  info "URL     : non lue automatiquement, voir :"
  info "  aws ecs describe-express-gateway-service --service-arn $SERVICE_ARN"
fi
info "Logs    : aws logs tail $LOG_GROUP --follow"
info "Detruire: ./infra/teardown.sh"
