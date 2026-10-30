#!/usr/bin/env bash
# Destroys the resources created by deploy.sh, to stop billing.
#
#   - ECS Express Mode service (ECS also removes its target group and
#     autoscaling; the ALB is shared and only goes once no service uses it)
#   - ECS cluster
#   - ECR repository and all its images
#   - CloudWatch log group
#   - IAM roles: only with --delete-iam (they are free, kept by default
#     to speed up the next deploy)
#
# Usage: ./infra/teardown.sh [-y] [--delete-iam]
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
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

echo "Region: $AWS_REGION"
echo "Resources to delete:"
echo "  - ECS Express service  $SERVICE_NAME (cluster $CLUSTER_NAME)"
echo "  - ECS cluster          $CLUSTER_NAME"
echo "  - ECR repository       $ECR_REPO (all images)"
echo "  - log group            $LOG_GROUP"
[[ "$DELETE_IAM" == true ]] && echo "  - IAM roles            $EXEC_ROLE_NAME, $INFRA_ROLE_NAME"

if [[ "$ASSUME_YES" != true ]]; then
  read -r -p "Confirm deletion? [y/N] " answer
  [[ "$answer" =~ ^[yYoO]$ ]] || { echo "Cancelled."; exit 0; }
fi

# --------------------------------------------------------------------------- #
# 1. Express service (must go first: it uses the infrastructure role)
# --------------------------------------------------------------------------- #
log "ECS Express service: $SERVICE_NAME"
service_status="$(aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" \
  --query 'services[0].status' --output text 2>/dev/null || true)"

if [[ "$service_status" == "ACTIVE" ]]; then
  SERVICE_ARN="$(aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" \
    --query 'services[0].serviceArn' --output text)"
  aws ecs delete-express-gateway-service --service-arn "$SERVICE_ARN" \
    --query 'service.status.statusCode' --output text
  info "Waiting for full shutdown (a few minutes)..."
  aws ecs wait services-inactive --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" \
    || info "Still being deleted, check the ECS console"
else
  info "Absent (status: ${service_status:-none})"
fi

# --------------------------------------------------------------------------- #
# 2. Cluster
# --------------------------------------------------------------------------- #
log "ECS cluster: $CLUSTER_NAME"
aws ecs delete-cluster --cluster "$CLUSTER_NAME" --query cluster.status --output text 2>/dev/null \
  || info "Absent or still used by another service"

# --------------------------------------------------------------------------- #
# 3. ECR repository
# --------------------------------------------------------------------------- #
log "ECR repository: $ECR_REPO"
aws ecr delete-repository --repository-name "$ECR_REPO" --force \
  --query repository.repositoryName --output text 2>/dev/null \
  || info "Absent"

# --------------------------------------------------------------------------- #
# 4. Log group
# --------------------------------------------------------------------------- #
log "Log group: $LOG_GROUP"
if aws logs delete-log-group --log-group-name "$LOG_GROUP" 2>/dev/null; then
  info "Deleted"
else
  info "Absent"
fi

# --------------------------------------------------------------------------- #
# 5. IAM roles (optional)
# --------------------------------------------------------------------------- #
delete_role() {
  local name="$1"
  if ! aws iam get-role --role-name "$name" >/dev/null 2>&1; then
    info "Role $name: absent"; return
  fi
  for policy in $(aws iam list-attached-role-policies --role-name "$name" \
                    --query 'AttachedPolicies[].PolicyArn' --output text); do
    aws iam detach-role-policy --role-name "$name" --policy-arn "$policy"
  done
  aws iam delete-role --role-name "$name"
  info "Role $name: deleted"
}

if [[ "$DELETE_IAM" == true ]]; then
  log "IAM roles"
  delete_role "$EXEC_ROLE_NAME"
  delete_role "$INFRA_ROLE_NAME"
fi

log "Done"
