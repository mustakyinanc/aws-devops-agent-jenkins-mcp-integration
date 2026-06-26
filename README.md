# DevOps Agent Jenkins MCP Integration

Connect AWS DevOps Agent to Jenkins using an MCP server running on AWS Lambda. Gives your agent full visibility into Jenkins — jobs, builds, pipelines, logs, agents, queue, plugins, and system info.

---

## Architecture

```
AWS DevOps Agent
      ↓  (SigV4)
Lambda Function URL
      ↓  (private IP)
Jenkins on EC2
```

The MCP server is a Python Lambda function running inside your VPC. It exposes 13 Jenkins tools to the DevOps Agent over a Lambda Function URL secured with AWS SigV4.

---

## What the agent can see

| Depth | Tools |
|---|---|
| Jobs | `list_jobs`, `trigger_build`, `abort_build` |
| Builds | `get_build_status`, `get_pipeline_stages`, `get_console_output`, `get_last_build`, `get_artifacts` |
| Config | `get_job_config` |
| System | `list_nodes`, `get_build_queue`, `list_plugins`, `get_system_info` |

---

## Quick start

See the full walkthrough in [step-by-step-guide.md](step-by-step-guide.md).

**Prerequisites:**
- Jenkins running on AWS EC2
- AWS CLI configured
- Python 3.12

**1. Clone the repo**
```bash
git clone https://github.com/mustakyinanc/aws-devops-agent-jenkins-mcp-integration.git
cd aws-devops-agent-jenkins-mcp-integration
```

**2. Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your Jenkins private IP, username, and API token
```

**3. Package and deploy**
```bash
mkdir package
pip install httpx -t package/
cp lambda_function.py package/
cd package && zip -r ../jenkins-mcp.zip . && cd ..

aws lambda create-function \
  --function-name jenkins-mcp \
  --runtime python3.12 \
  --architecture x86_64 \
  --role arn:aws:iam::YOUR-ACCOUNT-ID:role/lambda-jenkins-mcp-role \
  --handler lambda_function.handler \
  --zip-file fileb://jenkins-mcp.zip \
  --timeout 30 \
  --memory-size 128 \
  --vpc-config SubnetIds=YOUR-SUBNET-ID,SecurityGroupIds=YOUR-SG-ID
```

**4. Register with DevOps Agent**

Go to **DevOps Agent → Capability Providers → MCP Server → Register** and point it at your Lambda Function URL with SigV4 auth.

Full instructions in [step-by-step-guide.md](step-by-step-guide.md).

---

## Project structure

```
aws-devops-agent-jenkins-mcp-integration/
├── .gitignore
├── .env.example                # Environment variables template
├── README.md
├── lambda_function.py          # MCP server — all 13 Jenkins tools
├── step-by-step-guide.md       # Full setup walkthrough
└── policies/
    ├── lambda-trust-policy.json          # Trust policy for Lambda role
    ├── lambda-execution-policy.json      # Permissions for Lambda role
    ├── devops-agent-trust-policy.json    # Trust policy for DevOps Agent role
    └── devops-agent-invoke-policy.json   # Lambda invoke permission for DevOps Agent
```

---

## Security notes

- The Jenkins API token is stored as a Lambda environment variable. For production, move it to [AWS SSM Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
- Lambda communicates with Jenkins over the private VPC network — Jenkins port 8080 is never exposed to the internet
- The Lambda Function URL is secured with AWS SigV4 — only the DevOps Agent IAM role can invoke it

---

## License

MIT
