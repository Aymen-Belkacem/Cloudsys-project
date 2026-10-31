#!/usr/bin/env bash
# Deploys the Streamlit application to AWS:
#   1. DocumentDB password secret (asked once, stored in Secrets Manager)
#   2. Amazon ECR repository
#   3. Docker image build + push
#   4. IAM roles (execution + infrastructure) required by ECS Express Mode
#   5. CloudWatch log group
#   6. security group of the app + its access rule on DocumentDB
#   7. ECS cluster
#   8. ECS Express Mode service (created on first run, updated afterwards)
#   9. wait for stability + print the public URL
#
# The script can be re-run: each step checks whether the resource already exists.
# Usage (from WSL, at the project root or elsewhere): ./infra/deploy.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=infra/config.env
source "$SCRIPT_DIR/config.env"

export AWS_PAGER=""          # no "less" pager on AWS CLI output
export AWS_REGION

log()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
die()  { printf '\033[1;31mError: %s\033[0m\n' "$*" >&2; exit 1; }

# --------------------------------------------------------------------------- #
# 0. Prerequisites
# --------------------------------------------------------------------------- #
log "Checking prerequisites"
command -v aws    >/dev/null || die "AWS CLI not found"
command -v docker >/dev/null || die "Docker not found"
docker info >/dev/null 2>&1  || die "Docker is not responding (is Docker Desktop running, with WSL integration enabled?)"
aws ecs create-express-gateway-service --generate-cli-skeleton >/dev/null 2>&1 \
  || die "Your AWS CLI does not know ECS Express Mode: update it (recent AWS CLI v2)"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)" \
  || die "Invalid AWS credentials (aws configure?)"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
REPO_URI="${REGISTRY}/${ECR_REPO}"
info "Account: $ACCOUNT_ID | Region: $AWS_REGION"

# Image tag: short git hash if available, else a timestamp.
# A unique tag per deployment forces ECS to roll out a new revision.
if git -C "$PROJECT_ROOT" rev-parse --short HEAD >/dev/null 2>&1; then
  IMAGE_TAG="$(git -C "$PROJECT_ROOT" rev-parse --short HEAD)-$(date +%H%M%S)"
else
  IMAGE_TAG="$(date +%Y%m%d-%H%M%S)"
fi
IMAGE_URI="${REPO_URI}:${IMAGE_TAG}"

# --------------------------------------------------------------------------- #
# 1. DocumentDB password secret
# --------------------------------------------------------------------------- #
log "DocumentDB password secret: $DOCDB_SECRET_NAME"
if aws secretsmanager describe-secret --secret-id "$DOCDB_SECRET_NAME" >/dev/null 2>&1; then
  info "Already exists"
else
  read -r -s -p "    DocumentDB password for $DOCDB_USERNAME (hidden): " docdb_password \
    || die "No password given"
  echo
  [[ -n "$docdb_password" ]] || die "Empty password"
  # Passed through a private file: an argument would be visible in the process
  # list. The AWS CLI does not read file:///dev/stdin reliably.
  secret_file="$(mktemp)"
  trap 'rm -f "$secret_file"' EXIT
  printf '%s' "$docdb_password" > "$secret_file"
  unset docdb_password
  aws secretsmanager create-secret \
    --name "$DOCDB_SECRET_NAME" \
    --description "DocumentDB password of the Streamlit app" \
    --secret-string "file://$secret_file" \
    --query Name --output text
  rm -f "$secret_file"
fi
SECRET_ARN="$(aws secretsmanager describe-secret --secret-id "$DOCDB_SECRET_NAME" --query ARN --output text)"

# --------------------------------------------------------------------------- #
# 2. ECR repository
# --------------------------------------------------------------------------- #
log "ECR repository: $ECR_REPO"
if aws ecr describe-repositories --repository-names "$ECR_REPO" >/dev/null 2>&1; then
  info "Already exists"
else
  aws ecr create-repository \
    --repository-name "$ECR_REPO" \
    --image-scanning-configuration scanOnPush=true \
    --query repository.repositoryUri --output text
fi

# --------------------------------------------------------------------------- #
# 3. Image build + push
# --------------------------------------------------------------------------- #
log "Docker login to ECR"
aws ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY"

log "Building image: $IMAGE_URI"
# linux/amd64 = X86_64 architecture used by the Fargate service
docker build \
  --platform linux/amd64 \
  --build-arg APP_VERSION="$IMAGE_TAG" \
  -t "$IMAGE_URI" \
  "$PROJECT_ROOT"

log "Pushing image to ECR"
docker push "$IMAGE_URI"

# --------------------------------------------------------------------------- #
# 4. IAM roles
# --------------------------------------------------------------------------- #
ROLES_CREATED=false

# ensure_role <name> <service principal> <managed policy ARN>
ensure_role() {
  local name="$1" principal="$2" policy_arn="$3"
  if aws iam get-role --role-name "$name" >/dev/null 2>&1; then
    info "Role $name: already exists"
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
    info "Role $name: created"
    ROLES_CREATED=true
  fi
  # attach-role-policy is idempotent
  aws iam attach-role-policy --role-name "$name" --policy-arn "$policy_arn"
}

log "IAM roles"
# Execution role: used by the ECS agent to pull the ECR image and write logs
ensure_role "$EXEC_ROLE_NAME" "ecs-tasks.amazonaws.com" \
  "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
# Infrastructure role: used by ECS to create the ALB, target group, SG, autoscaling
ensure_role "$INFRA_ROLE_NAME" "ecs.amazonaws.com" \
  "arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices"

# Lets ECS read the password when it starts a task, and nothing else.
# put-role-policy is idempotent
aws iam put-role-policy \
  --role-name "$EXEC_ROLE_NAME" \
  --policy-name read-documentdb-secret \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": \"secretsmanager:GetSecretValue\",
      \"Resource\": \"$SECRET_ARN\"
    }]
  }"

EXEC_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${EXEC_ROLE_NAME}"
INFRA_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${INFRA_ROLE_NAME}"

if [[ "$ROLES_CREATED" == true ]]; then
  info "Waiting for IAM propagation (15 s)..."
  sleep 15
fi

# --------------------------------------------------------------------------- #
# 5. CloudWatch log group
# --------------------------------------------------------------------------- #
log "CloudWatch log group: $LOG_GROUP"
existing_lg="$(aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" \
  --query "logGroups[?logGroupName=='${LOG_GROUP}'].logGroupName | [0]" --output text)"
if [[ "$existing_lg" == "$LOG_GROUP" ]]; then
  info "Already exists"
else
  aws logs create-log-group --log-group-name "$LOG_GROUP"
  info "Created"
fi
aws logs put-retention-policy --log-group-name "$LOG_GROUP" --retention-in-days "$LOG_RETENTION_DAYS"

# --------------------------------------------------------------------------- #
# 6. Security group of the app + access rule on DocumentDB
# --------------------------------------------------------------------------- #
log "Security group: $APP_SG_NAME"
APP_SG_ID="$(aws ec2 describe-security-groups \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=$APP_SG_NAME" \
  --query 'SecurityGroups[0].GroupId' --output text)"
if [[ "$APP_SG_ID" == "None" ]]; then
  APP_SG_ID="$(aws ec2 create-security-group \
    --group-name "$APP_SG_NAME" \
    --description "Streamlit app tasks" \
    --vpc-id "$VPC_ID" \
    --query GroupId --output text)"
  info "Created: $APP_SG_ID"
else
  info "Already exists: $APP_SG_ID"
fi

log "DocumentDB access rule on $DOCDB_SG_ID"
if rule_output="$(aws ec2 authorize-security-group-ingress \
    --group-id "$DOCDB_SG_ID" \
    --protocol tcp --port 27017 \
    --source-group "$APP_SG_ID" 2>&1)"; then
  info "Created"
elif [[ "$rule_output" == *InvalidPermission.Duplicate* ]]; then
  info "Already exists"
else
  die "$rule_output"
fi

# --------------------------------------------------------------------------- #
# 7. ECS cluster
# --------------------------------------------------------------------------- #
log "ECS cluster: $CLUSTER_NAME"
# create-cluster returns the existing cluster if it is already ACTIVE
aws ecs create-cluster --cluster-name "$CLUSTER_NAME" --query cluster.status --output text

# --------------------------------------------------------------------------- #
# 8. ECS Express Mode service
# --------------------------------------------------------------------------- #
PRIMARY_CONTAINER=$(cat <<JSON
{
  "image": "${IMAGE_URI}",
  "containerPort": ${CONTAINER_PORT},
  "awsLogsConfiguration": { "logGroup": "${LOG_GROUP}", "logStreamPrefix": "ecs" },
  "environment": [
    { "name": "APP_ENV", "value": "aws" },
    { "name": "APP_VERSION", "value": "${IMAGE_TAG}" },
    { "name": "DOCDB_HOST", "value": "${DOCDB_HOST}" },
    { "name": "DOCDB_USERNAME", "value": "${DOCDB_USERNAME}" },
    { "name": "DOCDB_DATABASE", "value": "${DOCDB_DATABASE}" },
    { "name": "DOCDB_COLLECTION", "value": "${DOCDB_COLLECTION}" }
  ],
  "secrets": [
    { "name": "DOCDB_PASSWORD", "valueFrom": "${SECRET_ARN}" }
  ]
}
JSON
)
SCALING_TARGET="minTaskCount=${MIN_TASKS},maxTaskCount=${MAX_TASKS}"

NETWORK_ARGS=(--network-configuration "subnets=[${SUBNETS}],securityGroups=[${APP_SG_ID}]")

service_status="$(aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" \
  --query 'services[0].status' --output text 2>/dev/null || true)"

if [[ "$service_status" == "ACTIVE" ]]; then
  log "Updating Express service: $SERVICE_NAME"
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
  log "Creating Express service: $SERVICE_NAME"
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
info "Service: $SERVICE_ARN"

# --------------------------------------------------------------------------- #
# 9. Wait + URL
# --------------------------------------------------------------------------- #
log "Waiting for the service to stabilize (up to ~10 min the first time)..."
if ! aws ecs wait services-stable --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME"; then
  info "The service is not stable yet. Diagnostics:"
  info "  aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --query 'services[0].events[:5]'"
  info "  aws logs tail $LOG_GROUP --since 15m"
  exit 1
fi

ENDPOINT="$(aws ecs describe-express-gateway-service --service-arn "$SERVICE_ARN" \
  --query "service.activeConfigurations[0].ingressPaths[?accessType=='PUBLIC'].endpoint | [0]" \
  --output text 2>/dev/null || true)"

log "Deployment complete"
info "Image   : $IMAGE_URI"
if [[ -n "$ENDPOINT" && "$ENDPOINT" != "None" ]]; then
  [[ "$ENDPOINT" == http* ]] || ENDPOINT="https://${ENDPOINT}"
  info "URL     : $ENDPOINT"
  info "(DNS may take a few minutes to resolve after the first creation)"
else
  info "URL     : not read automatically, see:"
  info "  aws ecs describe-express-gateway-service --service-arn $SERVICE_ARN"
fi
info "Logs    : aws logs tail $LOG_GROUP --follow"
info "Destroy : ./infra/teardown.sh"
