#!/usr/bin/env bash
# Provision the ParallaX staging/production VM in AWS us-east-1 (implementation.md §9; workflow.md §12.1; owner P).
#
# Prerequisites (on the operator's machine — this is the step that needs the team AWS account):
#   aws configure            # or AWS_PROFILE=<profile>; region is forced to us-east-1 below
#   an EC2 key pair name in us-east-1 (KEY_NAME), or omit to use SSM Session Manager only
#
# Usage:
#   ENV_NAME=staging KEY_NAME=my-key ./deploy/aws/provision.sh
#   ENV_NAME=production KEY_NAME=my-key INSTANCE_TYPE=m6i.xlarge ./deploy/aws/provision.sh
#
# Creates (idempotently, tagged Project=parallax, Env=$ENV_NAME):
#   security group (80/443 from anywhere; 22 only from SSH_CIDR if given), an IAM role with SSM access and
#   read-only access to the public SPHEREx bucket, a 4 vCPU / 16 GB instance (m6i.xlarge default) with a
#   100 GB gp3 volume, an Elastic IP, and runs deploy/aws/bootstrap.sh as user-data.
# Prints the public IP and the next steps. Cost: ≈ $0.19/h for m6i.xlarge + EBS; stop it when idle.
set -euo pipefail
export AWS_DEFAULT_REGION=us-east-1
ENV_NAME=${ENV_NAME:-staging}
INSTANCE_TYPE=${INSTANCE_TYPE:-m6i.xlarge}
VOLUME_GB=${VOLUME_GB:-100}
KEY_NAME=${KEY_NAME:-}
SSH_CIDR=${SSH_CIDR:-}
REPO_URL=${REPO_URL:-https://github.com/<org>/<repo>.git}
BRANCH=${BRANCH:-main}
NAME="parallax-${ENV_NAME}"
HERE="$(cd "$(dirname "$0")" && pwd)"

command -v aws >/dev/null || { echo "aws CLI v2 is required"; exit 1; }
aws sts get-caller-identity >/dev/null || { echo "not logged in to AWS (aws configure / aws sso login)"; exit 1; }

VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
[ "$VPC_ID" != "None" ] || { echo "no default VPC in us-east-1; set one up or pass SUBNET_ID"; exit 1; }

SG_ID=$(aws ec2 describe-security-groups --filters Name=group-name,Values="$NAME" Name=vpc-id,Values="$VPC_ID" \
        --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)
if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
  SG_ID=$(aws ec2 create-security-group --group-name "$NAME" --description "ParallaX $ENV_NAME web" \
          --vpc-id "$VPC_ID" --query GroupId --output text)
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 80 --cidr 0.0.0.0/0
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 443 --cidr 0.0.0.0/0
  if [ -n "$SSH_CIDR" ]; then
    aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 22 --cidr "$SSH_CIDR"
  fi
fi

ROLE="$NAME-role"
if ! aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE" --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  aws iam attach-role-policy --role-name "$ROLE" --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
  aws iam create-instance-profile --instance-profile-name "$ROLE" >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$ROLE" --role-name "$ROLE"
  sleep 10   # instance profile propagation
fi

AMI=$(aws ssm get-parameter --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id \
      --query Parameter.Value --output text)
USER_DATA=$(mktemp)
sed -e "s|__REPO_URL__|$REPO_URL|" -e "s|__BRANCH__|$BRANCH|" -e "s|__ENV_NAME__|$ENV_NAME|" "$HERE/bootstrap.sh" > "$USER_DATA"

EXISTING=$(aws ec2 describe-instances --filters Name=tag:Name,Values="$NAME" Name=instance-state-name,Values=pending,running,stopped \
           --query 'Reservations[0].Instances[0].InstanceId' --output text)
if [ "$EXISTING" != "None" ] && [ -n "$EXISTING" ]; then
  echo "instance $EXISTING already exists for $NAME; not creating another"
  IID=$EXISTING
else
  IID=$(aws ec2 run-instances --image-id "$AMI" --instance-type "$INSTANCE_TYPE" \
        ${KEY_NAME:+--key-name "$KEY_NAME"} --security-group-ids "$SG_ID" \
        --iam-instance-profile Name="$ROLE" \
        --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=$VOLUME_GB,VolumeType=gp3,DeleteOnTermination=true}" \
        --metadata-options HttpTokens=required \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME},{Key=Project,Value=parallax},{Key=Env,Value=$ENV_NAME}]" \
        --user-data "file://$USER_DATA" --query 'Instances[0].InstanceId' --output text)
  aws ec2 wait instance-running --instance-ids "$IID"
fi
rm -f "$USER_DATA"

EIP=$(aws ec2 describe-addresses --filters Name=tag:Name,Values="$NAME" --query 'Addresses[0].PublicIp' --output text)
if [ "$EIP" = "None" ] || [ -z "$EIP" ]; then
  ALLOC=$(aws ec2 allocate-address --domain vpc --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=$NAME}]" \
          --query AllocationId --output text)
  aws ec2 associate-address --instance-id "$IID" --allocation-id "$ALLOC" >/dev/null
  EIP=$(aws ec2 describe-addresses --allocation-ids "$ALLOC" --query 'Addresses[0].PublicIp' --output text)
fi

cat <<EOF
$NAME: instance $IID, public IP $EIP (us-east-1)
Next (docs/deploy.md):
  1. DNS: point your host name at $EIP, set SITE_ADDRESS in /srv/parallax/.env on the VM.
  2. Connect: aws ssm start-session --target $IID   (or ssh ubuntu@$EIP)
  3. Watch bootstrap: sudo tail -f /var/log/parallax-bootstrap.log
  4. F12 from the VM (D runs, P reviews): cd /srv/parallax && ./deploy/aws/run_f12.sh
  5. GitHub: add secrets DEPLOY_HOST_${ENV_NAME^^}=$EIP and DEPLOY_SSH_KEY, or register the VM as a self-hosted
     runner (labels: self-hosted, parallax-vm) for nightly validation.
EOF
