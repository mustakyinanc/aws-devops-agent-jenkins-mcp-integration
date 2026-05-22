# Step-by-step integration guide

This guide walks you through connecting AWS DevOps Agent to Jenkins using an MCP server running on AWS Lambda. By the end, your DevOps Agent will have full visibility into your Jenkins — jobs, builds, pipelines, logs, agents, queue, plugins, and system info.

---

## What you need before you start

- A Jenkins server running on AWS EC2
- An AWS account with permissions to create Lambda functions, IAM roles, and Function URLs
- AWS CLI installed and configured on your machine
- Python 3.12

---

## Step 1 — Get your Jenkins API token

1. Open your Jenkins instance in the browser
2. Click your username in the top-right corner
3. Click **Configure**
4. Scroll down to **API Token**
5. Click **Add new token**
6. Give it a name — e.g. `devops-agent-token`
7. Click **Generate**
8. Copy the token value immediately — Jenkins only shows it once

---

## Step 2 — Find your Jenkins EC2 private IP

1. Go to **AWS Console → EC2 → Instances**
2. Click your Jenkins instance
3. Copy the **Private IPv4 address** — looks like `10.0.x.x`

You will use this as your `JENKINS_URL` — never the public IP, since Lambda communicates over the internal AWS network.

---

## Step 3 — Create the Lambda IAM role

```bash
aws iam create-role \
  --role-name lambda-jenkins-mcp-role \
  --assume-role-policy-document file://policies/lambda-trust-policy.json

aws iam put-role-policy \
  --role-name lambda-jenkins-mcp-role \
  --policy-name LambdaExecutionPolicy \
  --policy-document file://policies/lambda-execution-policy.json

aws iam attach-role-policy \
  --role-name lambda-jenkins-mcp-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole
```

---

## Step 4 — Package the Lambda function

```bash
mkdir package
pip install httpx -t package/
cp lambda_function.py package/
cd package && zip -r ../jenkins-mcp.zip . && cd ..
```

---

## Step 5 — Deploy the Lambda function

Replace `YOUR-SUBNET-ID`, `YOUR-SECURITY-GROUP-ID`, and `YOUR-ACCOUNT-ID` with your real values.

```bash
aws lambda create-function \
  --function-name jenkins-mcp \
  --runtime python3.12 \
  --architecture x86_64 \
  --role arn:aws:iam::YOUR-ACCOUNT-ID:role/lambda-jenkins-mcp-role \
  --handler lambda_function.handler \
  --zip-file fileb://jenkins-mcp.zip \
  --timeout 30 \
  --memory-size 128 \
  --vpc-config SubnetIds=YOUR-SUBNET-ID,SecurityGroupIds=YOUR-SECURITY-GROUP-ID
```

---

## Step 6 — Set environment variables on the Lambda function

```bash
aws lambda update-function-configuration \
  --function-name jenkins-mcp \
  --environment Variables="{
    JENKINS_URL=http://YOUR-EC2-PRIVATE-IP:8080,
    JENKINS_USER=admin,
    JENKINS_TOKEN=your-api-token-from-step-1
  }"
```

---

## Step 7 — Allow Lambda security group to reach Jenkins on port 8080

Go to **EC2 → Security Groups → your Jenkins security group → Inbound rules → Edit → Add rule**:

- Type: Custom TCP
- Port: 8080
- Source: the security group attached to your Lambda function

If the Lambda uses the same security group as Jenkins, add a self-referencing rule (source = the same security group ID).

---

## Step 8 — Create a Lambda Function URL

```bash
aws lambda create-function-url-config \
  --function-name jenkins-mcp \
  --auth-type AWS_IAM
```

Copy the Function URL from the output — it looks like:

```
https://abc123xyz.lambda-url.us-east-1.on.aws
```

---

## Step 9 — Test the connection

In the AWS Lambda console:

1. Go to your `jenkins-mcp` function
2. Click the **Test** tab
3. Create a new test event with this body:

```json
{
  "requestContext": {"http": {"method": "POST"}},
  "rawPath": "/",
  "body": "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{}}"
}
```

4. Click **Test**
5. In the **Response** section you should see all 13 tools listed

If you see `{"error": "timed out"}` — check Step 7. The security group rule is likely missing.

---

## Step 10 — Create the DevOps Agent IAM role

```bash
aws iam create-role \
  --role-name devopsagent-jenkins \
  --assume-role-policy-document file://policies/devops-agent-trust-policy.json

aws iam put-role-policy \
  --role-name devopsagent-jenkins \
  --policy-name InvokeJenkinsMcp \
  --policy-document file://policies/devops-agent-invoke-policy.json
```

**Important:** Edit `policies/devops-agent-trust-policy.json` and `policies/devops-agent-invoke-policy.json` first — replace `YOUR-ACCOUNT-ID` and `YOUR-REGION` with your real values.

---

## Step 11 — Register the MCP server with DevOps Agent

1. In the AWS Console go to **DevOps Agent → Capability Providers → MCP Server → Register**
2. Fill in:
   - **Name**: `jenkins-mcp`
   - **Endpoint URL**: your Lambda Function URL from Step 8
   - **Description**: `Full Jenkins visibility — jobs, builds, pipelines, logs, system`
3. Click **Next**
4. Select **AWS SigV4** as the authorization flow
5. Click **Next**
6. Fill in:
   - **IAM Role**: select `devopsagent-jenkins`
   - **AWS Region**: your region e.g. `us-east-1`
   - **Service Name**: `lambda`
7. **Do NOT** check "Connect to endpoint using a private connection" — private connections are not supported with SigV4
8. Click **Next** then **Submit**

---

## Step 12 — Add the MCP server to your Agent Space

1. Go to **DevOps Agent → your Agent Space → Capabilities tab**
2. In the **MCP Servers** section, click **Add**
3. Select `jenkins-mcp`
4. Choose which tools to allowlist

**Read-only tools (safe to enable immediately):**
- `list_jobs`
- `get_build_status`
- `get_pipeline_stages`
- `get_console_output`
- `get_last_build`
- `get_artifacts`
- `get_job_config`
- `list_nodes`
- `get_build_queue`
- `list_plugins`
- `get_system_info`

**Write tools (enable when ready):**
- `trigger_build`
- `abort_build`

---

## What the agent can do now

Ask your DevOps Agent questions like:

- *"Which Jenkins jobs are currently failing?"*
- *"Show me the console output for the last failed build of job X"*
- *"Are all my build agents online?"*
- *"What's sitting in the build queue right now?"*
- *"Trigger a build for job X"*
- *"Which plugins are installed on my Jenkins?"*

---

## Available MCP tools reference

| Tool | Description | Required params |
|---|---|---|
| `list_jobs` | All jobs and status | none |
| `trigger_build` | Start a job | `job_name` |
| `abort_build` | Stop a running build | `job_name`, `build_number` |
| `get_build_status` | Result of a build | `job_name`, `build_number` |
| `get_pipeline_stages` | Stage breakdown | `job_name`, `build_number` |
| `get_console_output` | Full log | `job_name`, `build_number` |
| `get_last_build` | Latest build status | `job_name` |
| `get_artifacts` | Build artifacts | `job_name`, `build_number` |
| `get_job_config` | Job XML config | `job_name` |
| `list_nodes` | Build agents | none |
| `get_build_queue` | Queue | none |
| `list_plugins` | Installed plugins | none |
| `get_system_info` | Jenkins version and info | none |

---

## Hardening for production

Once everything is working, consider these improvements:

1. Move `JENKINS_TOKEN` from a Lambda environment variable to **AWS SSM Parameter Store** (free) or **AWS Secrets Manager**
2. Restrict the Lambda Function URL to only accept requests signed by the DevOps Agent role
3. Enable **CloudWatch logging** on the Lambda function to monitor all agent calls to Jenkins
