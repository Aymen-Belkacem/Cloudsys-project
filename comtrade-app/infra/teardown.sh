#!/usr/bin/env bash
# Detruit les ressources creees par deploy.sh, pour arreter la facturation.
#
#   - service ECS Express Mode (ECS supprime aussi l'ALB, le target group,
#     les security groups et l'autoscaling qu'il avait crees)
#   - cluster ECS
#   - depot ECR et toutes ses images
#   - log group CloudWatch
#   - roles IAM : seulement avec --delete-iam (ils sont gratuits, on les garde
#     par defaut pour accelerer le prochain deploy)
#
# Usage : ./infra/teardown.sh [-y] [--delete-iam]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=infra/config.env
source "$SCRIPT_DIR/config.env"

export AWS_PAGER=""
export AWS_REGION

log()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }

ASSUME_YES=false
DELETE_IAM=false
for arg in "$@"; do
  case "$arg" in
    -y|--yes)     ASSUME_YES=true ;;
    --delete-iam) DELETE_IAM=true ;;
    *) echo "Option inconnue : $arg" >&2; exit 2 ;;
  esac
done

echo "Region : $AWS_REGION"
echo "Ressources a supprimer :"
echo "  - service ECS Express  $SERVICE_NAME (cluster $CLUSTER_NAME) + ALB gere"
echo "  - cluster ECS          $CLUSTER_NAME"
echo "  - depot ECR            $ECR_REPO (toutes les images)"
echo "  - log group            $LOG_GROUP"
[[ "$DELETE_IAM" == true ]] && echo "  - roles IAM            $EXEC_ROLE_NAME, $INFRA_ROLE_NAME"

if [[ "$ASSUME_YES" != true ]]; then
  read -r -p "Confirmer la suppression ? [y/N] " answer
  [[ "$answer" =~ ^[yYoO]$ ]] || { echo "Annule."; exit 0; }
fi

# --------------------------------------------------------------------------- #
# 1. Service Express (doit partir en premier : il utilise le role d'infra)
# --------------------------------------------------------------------------- #
log "Service ECS Express : $SERVICE_NAME"
service_status="$(aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" \
  --query 'services[0].status' --output text 2>/dev/null || true)"

if [[ "$service_status" == "ACTIVE" ]]; then
  SERVICE_ARN="$(aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" \
    --query 'services[0].serviceArn' --output text)"
  aws ecs delete-express-gateway-service --service-arn "$SERVICE_ARN" \
    --query 'service.status.statusCode' --output text
  info "Attente de l'arret complet (quelques minutes)..."
  aws ecs wait services-inactive --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" \
    || info "Toujours en cours de suppression, verifiez dans la console ECS"
else
  info "Absent (statut : ${service_status:-inexistant})"
fi

# --------------------------------------------------------------------------- #
# 2. Cluster
# --------------------------------------------------------------------------- #
log "Cluster ECS : $CLUSTER_NAME"
aws ecs delete-cluster --cluster "$CLUSTER_NAME" --query cluster.status --output text 2>/dev/null \
  || info "Absent ou encore utilise par un autre service"

# --------------------------------------------------------------------------- #
# 3. Depot ECR
# --------------------------------------------------------------------------- #
log "Depot ECR : $ECR_REPO"
aws ecr delete-repository --repository-name "$ECR_REPO" --force \
  --query repository.repositoryName --output text 2>/dev/null \
  || info "Absent"

# --------------------------------------------------------------------------- #
# 4. Log group
# --------------------------------------------------------------------------- #
log "Log group : $LOG_GROUP"
if aws logs delete-log-group --log-group-name "$LOG_GROUP" 2>/dev/null; then
  info "Supprime"
else
  info "Absent"
fi

# --------------------------------------------------------------------------- #
# 5. Roles IAM (optionnel)
# --------------------------------------------------------------------------- #
delete_role() {
  local name="$1"
  if ! aws iam get-role --role-name "$name" >/dev/null 2>&1; then
    info "Role $name : absent"; return
  fi
  for policy in $(aws iam list-attached-role-policies --role-name "$name" \
                    --query 'AttachedPolicies[].PolicyArn' --output text); do
    aws iam detach-role-policy --role-name "$name" --policy-arn "$policy"
  done
  aws iam delete-role --role-name "$name"
  info "Role $name : supprime"
}

if [[ "$DELETE_IAM" == true ]]; then
  log "Roles IAM"
  delete_role "$EXEC_ROLE_NAME"
  delete_role "$INFRA_ROLE_NAME"
fi

log "Termine"
