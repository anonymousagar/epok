import asyncio
import logging
import os
from temporalio.client import Client
from temporalio.worker import Worker

from workflows.spec_architecture import SpecArchitectureWorkflow
from activities.linear_activities import fetch_linear_issue_details
from activities.github_activities import inspect_repo_context, commit_code_patches
from activities.gemini_activities import generate_technical_spec
from activities.slack_activities import dispatch_slack_spec_approval
from activities.code_activities import generate_code_patches

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("epok.worker")


async def run_worker() -> None:
    temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    task_queue = os.getenv("EPOK_TASK_QUEUE", "epok-task-queue")

    logger.info(f"Connecting to Temporal server at {temporal_host} (namespace: {temporal_namespace})...")
    client = await Client.connect(temporal_host, namespace=temporal_namespace)

    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[SpecArchitectureWorkflow],
        activities=[
            fetch_linear_issue_details,
            inspect_repo_context,
            commit_code_patches,
            generate_technical_spec,
            dispatch_slack_spec_approval,
            generate_code_patches,
        ],
    )

    logger.info(f"Starting Epok Temporal Worker listening on task queue '{task_queue}'...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())

