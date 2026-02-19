# Certinator AI

Certinator AI is a multi-agent system that can effectively assist students in their preparation for Microsoft certification exams. The system is capable of understanding the exam syllabus, generating study plans, providing practice questions, and offering feedback on performance.

> [!NOTE]
> Certinator AI is an open-source project developed for the [Agents League content](https://github.com/microsoft/agentsleague). This app is competing in [Reasoning Agents track](https://github.com/microsoft/agentsleague/tree/main/starter-kits/2-reasoning-agents).

## Prerequisites

### Required Accounts
- **Microsoft Azure** (Access to Microsoft Foundry) - [azure.microsoft.com/free](https://aka.ms/azure-free-account)

### Required Tools
- **Python 3.12+** — [python.org/downloads](https://python.org/downloads)
- **uv** — [uv.pypa.io/en/stable/installation](https://uv.pypa.io/en/stable/installation) (Python task runner)
- **Node.js 20+** — [nodejs.org](https://nodejs.org) (for the frontend)
- **pnpm** — [pnpm.io](https://pnpm.io/installation) (Node package manager)

### Azure Subscription Notes
> [!IMPORTANT]
> Microsoft Foundry requires an Azure subscription. A **free trial** provides $200 credit for 30 days. Some features may incur costs after the trial. Check the [Azure pricing calculator](https://azure.microsoft.com/pricing/calculator/) to estimate costs.

## 🛠️ Environment Setup

### Step 1: Clone the Repository
```bash
git clone https://github.com/fernandosalomao/certinator-ai.git
cd app
```

### Step 2: Install dependencies using pnpm:
```bash
   pnpm install
```

  > **Note:** This automatically sets up the Python environment as well.
  >
  > If you have manual issues, you can run:
  >
  > ```sh
  > npm run install:agent
  > ```

### Step 3: Set Up Azure Credentials
Copy `.env.sample` to `.env` and fill in the values:

```bash
cp .env.sample .env
```

```env
# Find this in AI Foundry portal: Project settings → Project properties
AZURE_AI_PROJECT_ENDPOINT=your-project-endpoint-here

# Default model deployment name (required)
AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4.1
```

> [!WARNING]
> Never commit your `.env` file to GitHub! It's already in `.gitignore`.

> [!TIP]
> **Finding your project endpoint:**
> 1. Go to [Microsoft Foundry Portal](https://ai.azure.com)
> 2. Create or select your **AI Project**
> 3. In your project, go to **Project settings** (gear icon) → **Project properties**
> 4. Copy the **Project connection string**

## 🚀 Running the Application
```bash
pnpm dev
```
> This will start both the UI and the Microsoft Agent Framework server concurrently.

Open [http://localhost:3000](http://localhost:3000) for the full web UI.

### What You Get

The app runs a **complete multi-agent workflow** orchestrating 5 specialized agents:

1. **Coordinator** — Routes your query to the right specialist
2. **CertInfo** — Retrieves certification details (uses Microsoft Learn MCP)
3. **StudyPlan** — Generates personalized study schedules
4. **Practice** — Creates practice questions with feedback
5. **Critic** — Reviews specialist outputs for quality (accuracy, completeness, safety)

### Example Queries to Try

Once the UI opens, try these:

- **Certification info**: "Tell me about the AZ-104 certification and its prerequisites"
- **Study planning**: "Create a 6-week study plan for AZ-900. I can study 2 hours per day."
- **Practice questions**: "Give me 5 practice questions on Azure networking for AZ-104"

The workflow automatically routes your query through the coordinator → specialist → (optional critic review) → output.

## 🧪 Running Tests
```bash
python -m pytest tests/ -v
```

Or use the **"run tests"** task in VS Code (Terminal → Run Task).

## 📊 Running Evaluations
TBD

## 📁 Project Structure
TBD

## Contributing

Feel free to submit issues and enhancement requests!

## Troubleshooting

### Agent Connection Issues

If you see "I'm having trouble connecting to my tools", make sure:

1. The Microsoft Agent Framework agent is running on port 8000
2. Your environment variables are set correctly
3. Both servers started successfully

### Python Dependencies

If you encounter Python import errors:

```bash
cd agent
uv sync
uv run src/main.py
```
