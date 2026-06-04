#!/bin/bash
#
# Deploy the IDMS async broker service to AWS ECS Fargate.
#
# IDMS serves only the silent-SSO broker endpoints (/broker/*) under uvicorn,
# isolated from the main profiles app so a profiles slowdown can no longer
# starve broker redirects.
#
# IMPORTANT — shared state:
#   IDMS reads the SAME Django sessions and broker nonces as the main app, so
#   it MUST run with the SAME DJANGO_SECRET_KEY, the SAME database
#   (DATABASE_URL), the SAME Redis (REDIS_SERVER) and the SAME
#   STATIC_API_BEARER as the django task. The task definition therefore loads
#   the SAME environment file as the django task and only overrides
#   DJANGO_SETTINGS_MODULE=config.settings.idms. Point environmentFiles at the
#   django task's env source before deploying.
#
# Routing:
#   /broker/* is path-routed to this service on the same host as the profiles
#   app (see compose/production/traefik/traefik.yml broker-router). Add/enable
#   that rule LAST, after IDMS tasks are healthy — removing it is an instant
#   rollback, since the main app still serves /broker/* itself.
#
# Prerequisites:
# 1. AWS CLI configured with appropriate credentials
# 2. Docker installed and running
# 3. ECR repository created
# 4. ECS cluster created
# 5. IAM roles created (see setup-iam.sh)
# 6. The django environment file/secrets available to this task
#
# Usage:
#   ./aws/deploy-idms.sh [setup|build|push|deploy|all]
#

set -e

# Configuration - Update these values for your environment
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
ECR_REPOSITORY="hcommons-idms"
ECS_CLUSTER="hcommons-cluster"
ECS_SERVICE="hcommons-idms-service"
TASK_FAMILY="hcommons-idms"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Derived values
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"

echo "=== IDMS Broker Deployment ==="
echo "AWS Account: ${AWS_ACCOUNT_ID}"
echo "Region: ${AWS_REGION}"
echo "ECR Repository: ${ECR_URI}"
echo "ECS Cluster: ${ECS_CLUSTER}"
echo ""

setup_infrastructure() {
    echo "=== Setting up AWS infrastructure ==="

    # Create ECR repository if it doesn't exist
    echo "Creating ECR repository..."
    aws ecr describe-repositories --repository-names ${ECR_REPOSITORY} 2>/dev/null || \
        aws ecr create-repository \
            --repository-name ${ECR_REPOSITORY} \
            --image-scanning-configuration scanOnPush=true \
            --region ${AWS_REGION}

    # Create CloudWatch log group
    echo "Creating CloudWatch log group..."
    aws logs create-log-group \
        --log-group-name /ecs/${TASK_FAMILY} \
        --region ${AWS_REGION} 2>/dev/null || true

    echo "Infrastructure setup complete."
}

build_image() {
    echo "=== Building Docker image ==="

    cd "$(dirname "$0")/.."

    docker compose -f docker-compose.production.yml build idms

    echo "Build complete."
}

push_image() {
    echo "=== Pushing image to ECR ==="

    # Login to ECR
    aws ecr get-login-password --region ${AWS_REGION} | \
        docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

    # Tag and push
    docker tag knowledge_commons_profiles_production_idms:latest ${ECR_URI}:${IMAGE_TAG}
    docker tag knowledge_commons_profiles_production_idms:latest ${ECR_URI}:latest

    docker push ${ECR_URI}:${IMAGE_TAG}
    docker push ${ECR_URI}:latest

    echo "Push complete."
}

register_task_definition() {
    echo "=== Registering ECS task definition ==="

    cd "$(dirname "$0")"

    # Replace placeholders in task definition
    sed -e "s/ACCOUNT_ID/${AWS_ACCOUNT_ID}/g" \
        idms-task-definition.json > /tmp/idms-task-definition.json

    # Register the task definition
    aws ecs register-task-definition \
        --cli-input-json file:///tmp/idms-task-definition.json \
        --region ${AWS_REGION}

    rm /tmp/idms-task-definition.json

    echo "Task definition registered."
}

deploy_service() {
    echo "=== Deploying ECS service ==="

    # Check if service exists
    SERVICE_EXISTS=$(aws ecs describe-services \
        --cluster ${ECS_CLUSTER} \
        --services ${ECS_SERVICE} \
        --region ${AWS_REGION} \
        --query 'services[0].status' \
        --output text 2>/dev/null || echo "MISSING")

    if [ "${SERVICE_EXISTS}" = "ACTIVE" ]; then
        echo "Updating existing service..."
        aws ecs update-service \
            --cluster ${ECS_CLUSTER} \
            --service ${ECS_SERVICE} \
            --task-definition ${TASK_FAMILY} \
            --force-new-deployment \
            --region ${AWS_REGION}
    else
        echo "Creating new service..."
        echo "NOTE: You need to create the service manually or update this script"
        echo "with your VPC subnet and security group configuration. The service"
        echo "must be reachable by Traefik (same cluster/network) so /broker/* can"
        echo "be routed to it."
        echo ""
        echo "Example command:"
        echo "aws ecs create-service \\"
        echo "    --cluster ${ECS_CLUSTER} \\"
        echo "    --service-name ${ECS_SERVICE} \\"
        echo "    --task-definition ${TASK_FAMILY} \\"
        echo "    --desired-count 2 \\"
        echo "    --launch-type FARGATE \\"
        echo "    --network-configuration 'awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}' \\"
        echo "    --region ${AWS_REGION}"
    fi

    echo "Deployment complete."
}

print_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  setup   - Create ECR repository and CloudWatch log group"
    echo "  build   - Build Docker image locally"
    echo "  push    - Push image to ECR"
    echo "  deploy  - Register task definition and update/create service"
    echo "  all     - Run all steps (setup, build, push, deploy)"
    echo ""
    echo "Environment variables:"
    echo "  AWS_REGION       - AWS region (default: us-east-1)"
    echo "  AWS_ACCOUNT_ID   - AWS account ID (auto-detected)"
    echo "  IMAGE_TAG        - Docker image tag (default: latest)"
}

# Main
case "${1:-all}" in
    setup)
        setup_infrastructure
        ;;
    build)
        build_image
        ;;
    push)
        push_image
        ;;
    deploy)
        register_task_definition
        deploy_service
        ;;
    all)
        setup_infrastructure
        build_image
        push_image
        register_task_definition
        deploy_service
        ;;
    help|--help|-h)
        print_usage
        ;;
    *)
        echo "Unknown command: $1"
        print_usage
        exit 1
        ;;
esac

echo ""
echo "=== Done ==="
