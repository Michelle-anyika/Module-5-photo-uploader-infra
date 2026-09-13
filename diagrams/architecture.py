"""
Diagram-as-code for the Photo Uploader architecture.
Generates diagrams/architecture.png using the `diagrams` package (Graphviz).

    pip install diagrams
    (also requires Graphviz installed: https://graphviz.org/download/)
    python architecture.py
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import ECS, ECR
from diagrams.aws.database import RDS
from diagrams.aws.devtools import Codepipeline, Codedeploy
from diagrams.aws.integration import Eventbridge
from diagrams.aws.network import ALB, CloudFront, VPC, InternetGateway
from diagrams.aws.security import SecretsManager
from diagrams.aws.storage import S3
from diagrams.onprem.vcs import Github

graph_attr = {"fontsize": "14", "bgcolor": "white"}

with Diagram("Photo Uploader - AWS Architecture", filename="architecture", show=False, graph_attr=graph_attr, direction="TB"):

    github = Github("GitHub\n(app + infra repos)")
    users = InternetGateway("Users")

    with Cluster("CI/CD (GitHub Actions, OIDC)"):
        actions_to_ecr = ECR("ECR\nphoto-uploader")

    eventbridge = Eventbridge("EventBridge\nECR push rule")

    with Cluster("CodePipeline / CodeDeploy"):
        pipeline = Codepipeline("CodePipeline")
        codedeploy = Codedeploy("CodeDeploy\nBlue/Green")
        pipeline >> codedeploy

    cdn = CloudFront("CloudFront\n(Price Class 200, OAC)")

    with Cluster("VPC (multi-AZ)"):
        alb = ALB("Public ALB")

        with Cluster("Private subnets"):
            with Cluster("ECS Fargate Service (1-4 tasks)"):
                ecs_tasks = ECS("App tasks\n(FastAPI + React)")
            rds = RDS("RDS PostgreSQL\ndb.t3.micro")

        alb >> Edge(label="HTTP") >> ecs_tasks

    photos_bucket = S3("S3\nphotos bucket\n(private, OAC only)")
    secrets = SecretsManager("Secrets Manager\nDB credentials")

    github >> Edge(label="push app code") >> actions_to_ecr
    actions_to_ecr >> Edge(label="image push event") >> eventbridge >> pipeline

    users >> Edge(label="HTTPS") >> cdn >> Edge(label="OAC") >> photos_bucket
    users >> Edge(label="HTTP") >> alb

    ecs_tasks >> Edge(label="PutObject/GetObject") >> photos_bucket
    ecs_tasks >> Edge(label="metadata") >> rds
    ecs_tasks >> Edge(label="read creds") >> secrets
    codedeploy >> Edge(label="deploy new task set", style="dashed") >> ecs_tasks
