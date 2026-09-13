# Architecture diagram

`architecture.py` is diagram-as-code using the Python `diagrams` package
(renders via Graphviz). To generate `architecture.png`:

```bash
pip install diagrams
# Graphviz binary is also required: https://graphviz.org/download/
#   macOS:   brew install graphviz
#   Ubuntu:  sudo apt-get install graphviz
#   Windows: choco install graphviz  (or the installer from graphviz.org)
python architecture.py
```

Alternatively, recreate the same layout in draw.io/diagrams.net and export as PNG —
whichever is more convenient at submission time. The diagram should show:

- GitHub (app + infra repos) → GitHub Actions (OIDC) → ECR
- ECR push → EventBridge → CodePipeline → CodeDeploy (blue/green)
- VPC: public subnets (ALB) / private subnets (ECS tasks + RDS)
- ECS tasks → S3 (photos) and RDS (metadata) and Secrets Manager (DB creds)
- CloudFront (OAC) → S3 photos bucket, serving traffic to end users
- ALB → ECS tasks, serving the app to end users
