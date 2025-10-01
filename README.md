# GenTestAI
GentestAI is an **AI-powered testing companion** that watches code changes, generates structured test cases, and analyzes risk & quality in real time.  
It connects developers, testers, and QA teams by automatically producing **unit/integration test suggestions, validation checklists, and risk assessments** via **StarCoder2** and **Mistral** models.
It connects multiple AI services (StarCoder, Mistral) and exposes results through a **Node.js API** and a **React dashboard**.

---

## 🚀 Features
- 📡 **Watcher Service** — Detects local file changes and sends them to the main server.
- **AI Services**
  - **StarCoder Service** (`/generate-testcases`)
    - Uses NVIDIA-hosted `starcoder2-7b`
    - Generates structured JSON test cases
  - **Mistral Service** (`/analyze`)
    - Uses NVIDIA-hosted `mistral-7b-instruct-v0.3`
    - Produces risk scores, edge cases, and security recommendations

- **Frontend Dashboard (React + Vite)**
  - Clean and responsive dashboard layout
  - Panels:
    - **SummaryPanel** → high-level change summary
    - **PredictorPanel** → risk & impact prediction
    - **RecommenderPanel** → actionable test recommendations
  - Context-managed state (`AnalysisContext` + `UIContext`)

---

## 🛠️ Tech Stack

### Backend
- **Node.js** + Express
- **MySQL** (with `mysql2/promise`)
- **Axios** for service-to-service communication
- **Winston** for logging

### AI Models
- **StarCoder** (test case generation)
- **Mistral** (risk & security analysis)

### Frontend
- **React (Vite + TypeScript)**
- Context API for state management
- Tailwind CSS for styling
