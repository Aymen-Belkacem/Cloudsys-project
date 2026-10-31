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
#   - app security group, its DocumentDB rule and the password secret: only
#     with --delete-db-access (kept by default, the next deploy would ask for
#     the password again)
#
# Usage: ./infra/teardown.sh [-y] [--delete-iam] [--delete-db-access]
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
DELETE_DB_ACCESS=false
for arg in "$@"; do
  case "$arg" in
    -y|--yes)     ASSUME_YES=true ;;
    --delete-iam) DELETE_IAM=true ;;
    --delete-db-access) DELETE_DB_ACCESS=true ;;
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
[[ "$DELETE_DB_ACCESS" == true ]] && echo "  - DB access            $APP_SG_NAME + rule on $DOCDB_SG_ID, secret $DOCDB_SECRET_NAME"

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
  for policy in $(aws iam list-role-policies --role-name "$name" \
                    --query 'PolicyNames[]' --output text); do
    aws iam delete-role-policy --role-name "$name" --policy-name "$policy"
  done
  aws iam delete-role --role-name "$name"
  info "Role $name: deleted"
}

if [[ "$DELETE_IAM" == true ]]; then
  log "IAM roles"
  delete_role "$EXEC_ROLE_NAME"
  delete_role "$INFRA_ROLE_NAME"
fi

# --------------------------------------------------------------------------- #
# 6. DocumentDB access (optional)
# --------------------------------------------------------------------------- #
if [[ "$DELETE_DB_ACCESS" == true ]]; then
  log "Security group: $APP_SG_NAME"
  app_sg_id="$(aws ec2 describe-security-groups \
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=$APP_SG_NAME" \
    --query 'SecurityGroups[0].GroupId' --output text)"
  if [[ "$app_sg_id" == "None" ]]; then
    info "Absent"
  else
    # The rule must go first: it references the security group
    aws ec2 revoke-security-group-ingress \
      --group-id "$DOCDB_SG_ID" \
      --protocol tcp --port 27017 \
      --source-group "$app_sg_id" >/dev/null 2>&1 \
      || info "Rule on $DOCDB_SG_ID: absent"
    if aws ec2 delete-security-group --group-id "$app_sg_id" 2>/dev/null; then
      info "Deleted"
    else
      info "Still in use by the service being deleted, run this script again later"
    fi
  fi

  log "Secret: $DOCDB_SECRET_NAME"
  aws secretsmanager delete-secret --secret-id "$DOCDB_SECRET_NAME" \
    --force-delete-without-recovery >/dev/null
  info "Deleted"
fi

log "Done"
