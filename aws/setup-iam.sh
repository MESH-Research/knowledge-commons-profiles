#!/bin/bash
#
# Set up IAM roles for Website Monitor ECS Task
#
# This script creates:
# 1. Task execution role (for ECS to pull images and write logs)
# 2. Task role (for the monitor to modify ALB rules)
#
# Usage:
#   ./aws/setup-iam.sh
#

set -e

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"

TASK_ROLE_NAME="hcommons-monitor-task-role"
EXECUTION_ROLE_NAME="ecsTaskExecutionRole"

echo "=== Setting up IAM roles for Monitor ==="
echo "AWS Account: ${AWS_ACCOUNT_ID}"
echo "Region: ${AWS_REGION}"
echo ""

# Trust policy for ECS tasks
TRUST_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}'

# Create task execution role if it doesn't exist
echo "=== Creating Task Execution Role ==="
if ! aws iam get-role --role-name ${EXECUTION_ROLE_NAME} 2>/dev/null; then
    aws iam create-role \
        --role-name ${EXECUTION_ROLE_NAME} \
        --assume-role-policy-document "${TRUST_POLICY}"

    aws iam attach-role-policy \
        --role-name ${EXECUTION_ROLE_NAME} \
        --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

    echo "Created ${EXECUTION_ROLE_NAME}"
else
    echo "${EXECUTION_ROLE_NAME} already exists"
fi

# Add Secrets Manager permissions to execution role
echo "Adding Secrets Manager permissions..."
SECRETS_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:'${AWS_REGION}':'${AWS_ACCOUNT_ID}':secret:hcommons/*"
    }
  ]
}'

aws iam put-role-policy \
    --role-name ${EXECUTION_ROLE_NAME} \
    --policy-name SecretsManagerAccess \
    --policy-document "${SECRETS_POLICY}" 2>/dev/null || true

# Create task role for ALB access
echo ""
echo "=== Creating Task Role ==="
if ! aws iam get-role --role-name ${TASK_ROLE_NAME} 2>/dev/null; then
    aws iam create-role \
        --role-name ${TASK_ROLE_NAME} \
        --assume-role-policy-document "${TRUST_POLICY}"

    echo "Created ${TASK_ROLE_NAME}"
else
    echo "${TASK_ROLE_NAME} already exists"
fi

# ALB modification policy
echo "Adding ALB modification permissions..."
ALB_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:DescribeRules",
        "elasticloadbalancing:ModifyRule"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:DescribeListeners",
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DescribeTargetGroups"
      ],
      "Resource": "*"
    }
  ]
}'

aws iam put-role-policy \
    --role-name ${TASK_ROLE_NAME} \
    --policy-name ALBModifyAccess \
    --policy-document "${ALB_POLICY}"

echo ""
echo "=== IAM Setup Complete ==="
echo ""
echo "Task Execution Role ARN: arn:aws:iam::${AWS_ACCOUNT_ID}:role/${EXECUTION_ROLE_NAME}"
echo "Task Role ARN: arn:aws:iam::${AWS_ACCOUNT_ID}:role/${TASK_ROLE_NAME}"
echo ""
echo "Next steps:"
echo "1. Create secrets in AWS Secrets Manager:"
echo "   aws secretsmanager create-secret --name hcommons/sparkpost \\"
echo "       --secret-string '{\"api_key\":\"YOUR_KEY\",\"api_url\":\"https://api.sparkpost.com/api/v1\"}'"
echo ""
echo "2. Update aws/monitor-task-definition.json with your account ID"
echo ""
echo "3. Run: ./aws/deploy-monitor.sh all"
