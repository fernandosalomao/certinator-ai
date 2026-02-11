# Certinator AI

Certinator AI is a multi-agent system that can effectively assist students in their preparation for Microsoft certification exams. The system is capable of understanding the exam syllabus, generating study plans, providing practice questions, and offering feedback on performance.

> [!NOTE]
> Certinator AI is an open-source project developed for the [Agents League content](https://github.com/microsoft/agentsleague). This app is competing in [Reasoning Agents track](https://github.com/microsoft/agentsleague/tree/main/starter-kits/2-reasoning-agents).

## Prerequisites

### Required Accounts
- **Microsoft Azure** (Access to Microsoft Foundry) - [azure.microsoft.com/free](https://aka.ms/azure-free-account)

### Required Tools
- **Python 3.10+** — [python.org/downloads](https://python.org/downloads)

### Azure Subscription Notes
> [!IMPORTANT]
> Microsoft Foundry requires an Azure subscription. A **free trial** provides $200 credit for 30 days. Some features may incur costs after the trial. Check the [Azure pricing calculator](https://azure.microsoft.com/pricing/calculator/) to estimate costs.

## 🛠️ Environment Setup

### Step 1: Clone the Repository
```bash
git clone https://github.com/fernandosalomao/certinator-ai.git
cd app
```

### Step 2: Create a Python Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Set Up Azure Credentials

1. Go to [Microsoft Foundry Portal](https://ai.azure.com)
2. Create or select your **AI Project**
3. In your project, go to **Project settings** (gear icon) → **Project properties**
4. Copy the **Project connection string**
5. Create a `.env` file in this directory:

```env
# Option 1: Use Project Connection String (Recommended)
# Find this in AI Foundry portal: Project settings → Project properties
AZURE_AI_PROJECT_CONNECTION_STRING=your-connection-string-here

# Option 2: Use Individual Settings
# AZURE_SUBSCRIPTION_ID=your-subscription-id
# AZURE_RESOURCE_GROUP=your-resource-group
# AZURE_AI_PROJECT_NAME=your-project-name

# Model Deployment Name (from your project's Deployments)
AZURE_AI_MODEL_DEPLOYMENT=gpt-4o
```

> [!TIP]
> **Finding your connection string:**
> 1. Open [ai.azure.com](https://ai.azure.com)
> 2. Select your project
> 3. Click the gear icon (Project settings) → Project properties
> 4. Copy the "Project connection string"

> [!WARNING]
> Never commit your `.env` file to GitHub! It's already in `.gitignore`.

### Step 4: Install Dependencies
```bash
pip install -r requirements.txt
```

## 🚀 Running the Application

```bash
python main.py
```

### DevUI 
TBD

## Architecture Overview

``` 