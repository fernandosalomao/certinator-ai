# Certinator AI

Certinator AI is a multi-agent system that can effectively assist students in their preparation for Microsoft certification exams. The system is capable of understanding the exam syllabus, generating study plans, providing practice questions, and offering feedback on performance.

> [!NOTE]
> Certinator AI is an open-source project developed for the [Agents League content](https://github.com/microsoft/agentsleague). This app is competing in [Reasoning Agents track](https://github.com/microsoft/agentsleague/tree/main/starter-kits/2-reasoning-agents).

## Prerequisites

### Required Accounts
- **Microsoft Azure** (Access to Microsoft Foundry) - [azure.microsoft.com/free](https://aka.ms/azure-free-account)

### Required Tools
- **Python 3.12+** — [python.org/downloads](https://python.org/downloads)
- **Node.js 18+** and **pnpm** — [nodejs.org](https://nodejs.org/) / [pnpm.io](https://pnpm.io/installation)

### Azure Subscription Notes
> [!IMPORTANT]
> Microsoft Foundry requires an Azure subscription. A **free trial** provides $200 credit for 30 days. Some features may incur costs after the trial. Check the [Azure pricing calculator](https://azure.microsoft.com/pricing/calculator/) to estimate costs.

## 🚀 Quick Start (Choose One)

### Option 1: Command Line (Recommended)

```bash
# 1. Clone and enter the repo
git clone https://github.com/fernandosalomao/certinator-ai.git
cd certinator-ai

# 2. Configure environment
cp .env.sample .env
# Edit .env with your Azure credentials

# 3. Install all dependencies
make install

# 4. Start both backend + frontend
make dev
```

**Press `Ctrl+C` to stop both services.**

Other useful commands:
- `make help` — Show all available commands
- `make stop` — Force stop all processes
- `make logs` — Tail backend logs

### Option 2: VS Code Tasks

1. Open the project in VS Code
2. Press `Ctrl+Shift+P` → **Tasks: Run Task**
3. Select **🚀 Start Certinator (Full App)**

**To stop:** Run task **⏹️ Stop All**

### Option 3: Dev Container (GitHub Codespaces / Docker)

1. Open in GitHub Codespaces or VS Code with Dev Containers extension
2. Wait for automatic setup (installs all dependencies)
3. Configure `.env` with your credentials
4. Run `make dev` or use VS Code task **🚀 Start Certinator**

> [!TIP]
> The dev container automatically forwards ports 3000 (frontend) and 8087 (backend).

---

## 🛠️ Manual Environment Setup

<details>
<summary>Click to expand manual setup instructions</summary>

### Step 1: Clone the Repository
```bash
git clone https://github.com/fernandosalomao/certinator-ai.git
cd certinator-ai
```

### Step 2: Install Backend Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3: Install Frontend Dependencies
```bash
cd frontend
pnpm install
cd ..
```

### Step 4: Configure Environment
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

### Step 5: Run Services Separately

**Backend:**
```bash
source .venv/bin/activate
python src/app.py --agui
```

**Frontend (in another terminal):**
```bash
cd frontend
pnpm dev
```

</details>

---

## 🌐 Access the Application

Once running:
- **Frontend UI:** http://localhost:3000
- **Backend API:** http://localhost:8087

## 🤖 What You Get

The app runs a **complete multi-agent workflow** orchestrating 6 specialized agents:

1. **CoordinatorAgent** — Routes your query to the right specialist
2. **CertificationInfoAgent** — Retrieves certification details
3. **LearningPathFetcherAgent** — Retrieves learning paths for certifications
4. **StudyPlanGeneratorAgent** — Generates personalized study schedules
5. **PracticeQuestionsAgent** — Creates practice questions with feedback
6. **CriticAgent** — Reviews specialist outputs for quality (accuracy, completeness, safety)

### Example Queries to Try

Once the UI opens, try these:

- **Certification info**: "Tell me about the AZ-104 certification and its prerequisites"
- **Study planning**: "Create a 6-week study plan for AZ-900. I can study 2 hours per day."
- **Practice questions**: "Give me 5 practice questions on Azure networking for AZ-104"

The workflow automatically routes your query through the coordinator → specialist → (optional critic review) → output.

## 🧪 Running Tests
TBD

## 🐞 Debugging with AI Toolkit Agent Inspector
TBD

## 📊 Running Evaluations
TBD

## 📁 Project Structure
TBD

## Contributing

Feel free to submit issues and enhancement requests!

## Troubleshooting

### Agent Connection Issues

