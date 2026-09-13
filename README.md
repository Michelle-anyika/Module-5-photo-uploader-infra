# Photo Uploader – Infrastructure

CloudFormation templates for the Photo Uploader app: multi-AZ VPC, private ECS/Fargate
service behind a public ALB, RDS PostgreSQL, S3 + CloudFront (OAC-restricted), ECR,
and a CodePipeline/CodeDeploy blue-green pipeline triggered by EventBridge on ECR pushes.

Application code lives in a separate repo: `photo-uploader-app`.

## Stack deploy order

Stacks are independent CloudFormation stacks linked via `Export`/`Fn::ImportValue`
(no nested-stack packaging needed). Deploy in this order — each stage depends on
exports from the previous one:

1. `network.yaml`
2. `security.yaml`
3. `endpoints.yaml`, `storage.yaml`, `ecr.yaml` (parallel — no interdependencies)
4. `database.yaml`
5. `iam.yaml` (needs `GitHubOrg` / `GitHubAppRepo` params, storage + ecr + database ARNs)
6. `cdn.yaml`
7. `alb.yaml`
8. `ecs.yaml`
9. `pipeline.yaml`

```bash
STACK_PREFIX=photo-uploader-prod
REGION=us-east-1

aws cloudformation deploy --stack-name ${STACK_PREFIX}-network   --template-file templates/network.yaml   --region $REGION
aws cloudformation deploy --stack-name ${STACK_PREFIX}-security  --template-file templates/security.yaml  --region $REGION
aws cloudformation deploy --stack-name ${STACK_PREFIX}-endpoints --template-file templates/endpoints.yaml --region $REGION
aws cloudformation deploy --stack-name ${STACK_PREFIX}-storage   --template-file templates/storage.yaml   --region $REGION
aws cloudformation deploy --stack-name ${STACK_PREFIX}-ecr       --template-file templates/ecr.yaml       --region $REGION
aws cloudformation deploy --stack-name ${STACK_PREFIX}-database  --template-file templates/database.yaml  --region $REGION

aws cloudformation deploy --stack-name ${STACK_PREFIX}-iam --template-file templates/iam.yaml --region $REGION \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides GitHubOrg=<your-org> GitHubAppRepo=photo-uploader-app \
    EcrRepositoryArn=$(aws cloudformation describe-stacks --stack-name ${STACK_PREFIX}-ecr --query "Stacks[0].Outputs[?OutputKey=='RepositoryArn'].OutputValue" --output text) \
    DBSecretArn=$(aws cloudformation describe-stacks --stack-name ${STACK_PREFIX}-database --query "Stacks[0].Outputs[?OutputKey=='DBSecretArn'].OutputValue" --output text) \
    PhotosBucketArn=$(aws cloudformation describe-stacks --stack-name ${STACK_PREFIX}-storage --query "Stacks[0].Outputs[?OutputKey=='PhotosBucketArn'].OutputValue" --output text) \
    PipelineArtifactsBucketArn=$(aws cloudformation describe-stacks --stack-name ${STACK_PREFIX}-storage --query "Stacks[0].Outputs[?OutputKey=='PipelineArtifactsBucketArn'].OutputValue" --output text)

aws cloudformation deploy --stack-name ${STACK_PREFIX}-cdn --template-file templates/cdn.yaml --region $REGION
aws cloudformation deploy --stack-name ${STACK_PREFIX}-alb --template-file templates/alb.yaml --region $REGION
aws cloudformation deploy --stack-name ${STACK_PREFIX}-ecs --template-file templates/ecs.yaml --region $REGION
aws cloudformation deploy --stack-name ${STACK_PREFIX}-pipeline --template-file templates/pipeline.yaml --region $REGION
```

All templates default `ProjectName=photo-uploader` / `Environment=prod`, so exports
line up automatically as long as you keep those two parameters consistent across
every stack in an environment.

## CloudFormation Git Sync

For the actual submission, connect this repo via **CloudFormation → Git sync**
(uses a CodeConnections connection to GitHub). Point it at `templates/` and map
each template to a stack using the same names/order as above — Git sync then
deploys automatically on every push to `main`, which satisfies the "provisioned
via CloudFormation GitSync" requirement without any separate CI pipeline for
infrastructure.

## Deployment pipeline flow

1. GitHub Actions in `photo-uploader-app` builds the image and `docker push`es to
   ECR (OIDC-authenticated), and uploads `config/appspec-source.zip`
   (`appspec.yaml` + `taskdef.json`) to the pipeline artifacts bucket.
2. The ECR push emits an `ECR Image Action` event; `EcrPushRule` (in
   `pipeline.yaml`) matches it and starts the CodePipeline execution.
3. CodePipeline pulls the new image reference + the appspec/taskdef config, and
   hands off to CodeDeploy, which stands up the **green** task set, shifts ALB
   traffic from the **blue** target group, and terminates blue after a 5-minute
   bake time (or rolls back automatically on failed health checks).

## Notes / trade-offs

- No NAT Gateway — private subnets reach ECR/S3/CloudWatch/Secrets Manager purely
  through VPC endpoints, which is both cheaper and keeps ECS tasks with no
  route to the public internet at all.
- `MultiAZ` for RDS defaults to `false` to control cost for a lab; flip to `true`
  for a production-grade deployment.
- The ECS `Service` resource is only for bootstrapping — once CodeDeploy owns
  the service (`DeploymentController: CODE_DEPLOY`), further deployments must go
  through CodeDeploy/CodePipeline, not stack updates to `ecs.yaml`.
