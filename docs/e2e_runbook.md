# Epok End-to-End (E2E) Sandbox Runbook & Deployment Manual

Welcome to the **Epok Operational Runbook**. Epok is an autonomous multi-agent feature delivery & review swarm that ingests Linear issues, generates technical architecture specs with Gemini 2.5 Flash, gates deployment behind interactive Slack Block Kit approvals, automatically generates code patches and Pull Requests on GitHub, and self-heals CI build failures.

---

## 1. Architecture Overview & Components

```
   ┌──────────────────┐
   │   Linear Issue   │
   └────────┬─────────┘
            │ Webhook POST /webhooks/linear
            ▼
   ┌─────────────────────────────────────────┐
   │         FastAPI Webhook Gateway         │
   └────────┬────────────────────────────────┘
            │ Start Temporal Workflow
            ▼
┌────────────────────────────────────────────────────────┐
│     FeatureDeliveryLifecycleWorkflow (Temporal)        │
│                                                        │
│  Phase 1: Ingest Context (Linear & GitHub Repo Tree)   │
│  Phase 2: Generate Architecture Spec (Gemini Flash)    │
│  Phase 3: Interactive Slack Spec Approval Card         │
│           └─ Developer Clicks "Approve Spec"           │
│  Phase 4: Code Generation & GitHub PR Creation         │
│  Phase 5: CI Watchdog & Self-Healing Repair Loop       │
│  Phase 6: Linear & Slack Status Synchronization        │
└────────────────────────────────────────────────────────┘
```

---

## 2. Local Development & Sandbox Environment

### Prerequisites
* Python 3.9+
* Docker & Docker Compose
* GitHub Personal Access Token (`repo` scope)
* Gemini API Key (`GEMINI_API_KEY`)
* Linear API Key (`LINEAR_API_KEY`)
* Slack Bot Token (`SLACK_BOT_TOKEN`)

### Step 2.1: Start Local Services
Launch PostgreSQL, Temporal Server, and Temporal UI:
```bash
docker-compose up -d
```
* **Temporal Web UI**: [http://localhost:8233](http://localhost:8233)
* **Postgres DB**: `localhost:5432` (`epok_user`/`epok_pass`)

### Step 2.2: Setup Python Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Step 2.3: Configure Local Environment Variables
Create a local `.env` file:
```bash
export GEMINI_API_KEY="AIzaSy..."
export GITHUB_TOKEN="ghp_..."
export SLACK_BOT_TOKEN="xoxb-..."
export LINEAR_API_KEY="lin_api_..."
export LINEAR_WEBHOOK_SECRET="secret_linear"
export GITHUB_WEBHOOK_SECRET="secret_github"
export SLACK_SIGNING_SECRET="secret_slack"
export TEMPORAL_HOST="localhost:7233"
export EPOK_TASK_QUEUE="epok-task-queue"
```

### Step 2.4: Launch Local Services
1. **Launch Temporal Worker**:
   ```bash
   python src/worker/worker.py
   ```
2. **Launch Webhook Gateway API**:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8080 --reload
   ```

---

## 3. Production Deployment on GCP (Cloud Run & Cloud SQL)

### Step 3.1: Build & Push Docker Image
```bash
docker build -t gcr.io/<YOUR_GCP_PROJECT>/epok-app:latest .
docker push gcr.io/<YOUR_GCP_PROJECT>/epok-app:latest
```

### Step 3.2: Deploy Infrastructure via Terraform
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your GCP project ID & image URI
terraform init
terraform apply
```

---

## 4. Webhook URL Configuration

Set the following webhook endpoints in your external developer tools:

| Platform | Event Trigger | Webhook Target URL |
| :--- | :--- | :--- |
| **Linear** | Issue Created / Updated | `https://<CLOUD_RUN_URL>/webhooks/linear` |
| **GitHub** | `workflow_run.completed` | `https://<CLOUD_RUN_URL>/webhooks/github` |
| **Slack** | Interactive Button Actions | `https://<CLOUD_RUN_URL>/webhooks/slack` |

---

## 5. End-to-End Verification Scenario

1. **Trigger Issue**: Create a ticket in Linear titled `"Add User Authentication Endpoint"`.
2. **Spec Generation**: Observe Temporal UI (`http://localhost:8233`) as `FeatureDeliveryLifecycleWorkflow` executes `fetch_linear_issue_details`, `inspect_repo_context`, and `generate_technical_spec`.
3. **Slack Approval**: Check your Slack approval channel (`#epok-approvals`). Click **"Approve Spec"**.
4. **Code Delivery**: Epok generates file patches, creates branch `epok/issue-<ID>`, commits code, and opens a GitHub Pull Request.
5. **CI Watchdog**: If GitHub Actions CI fails, `CIRepairWorkflow` catches the failure, inspects error traces, generates fix commits, and pushes up to 3 repair iterations.
6. **State Sync**: Linear issue status updates to `In Review` with PR link attached, and Slack notification card updates to `PR Submitted & In Review`.
