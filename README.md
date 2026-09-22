# NDATrace — Evidence-Grounded NDA Requirement Review

A modular Python AI pipeline that takes an NDA document and a confidentiality requirement, retrieves relevant clauses, classifies the requirement as **Entailment / Contradiction / Not Mentioned**, and shows the exact evidence supporting that classification.

**Course:** NTU PE6201 Emerging AI Technologies — End-of-Course Project  
**Author:** Asmitha Ubaidulla  
**Deadline:** 4 October 2026

## Architecture

Synchronous modular monolith:
- **Pipeline** (`pipeline/`): Parser → Chunker → Embedder → Retriever → Classifier → Evidence Validator → Confidence/Abstention → Selective Agent
- **Backend** (`backend/`): FastAPI with Pydantic request/response contracts
- **Frontend** (`frontend/`): Next.js + React + TypeScript
- **Persistence**: SQLite (product) + JSONL (experiments)
- **Vector Search**: FAISS (local, in-process)

## Quick Start

```bash
# 1. Clone and set up environment
git clone <repo-url>
cd ndatrace
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your OpenRouter API key

# 4. Download ContractNLI dataset
bash scripts/download_data.sh

# 5. Verify environment
python scripts/verify_environment.py

# 6. Start the backend
uvicorn backend.app:app --reload

# 7. Start the frontend (in another terminal)
cd frontend && npm install && npm run dev
```

## Project Structure

```
ndatrace/
├── pipeline/          # AI pipeline modules (production code)
├── prompts/           # Versioned prompt templates
├── evaluation/        # Evaluation harness (metrics, scoring)
├── experiments/       # Experiment configurations
├── notebooks/         # Jupyter notebooks (exploration)
├── backend/           # FastAPI application
├── frontend/          # Next.js application
├── results/           # Experiment results (append-only)
├── data/              # Dataset and golden test cases
├── tests/             # Test suite
├── scripts/           # CLI utilities
└── docs/              # Documentation
```

## Key Metrics

| Metric | Description |
|--------|-------------|
| Joint Label+Evidence Correctness | Correct label AND correct evidence retrieval |
| Macro-F1 | Equal weight to all three classes |
| Risk-Sensitive Recall | Focus on Contradiction and Not Mentioned |
| Abstention Effectiveness | Are abstained cases actually hard? |

## Dataset

[ContractNLI](https://stanfordnlp.github.io/contract-nli/) — 607 NDAs with 17 confidentiality hypotheses, annotated with labels and evidence spans.

## License

Academic project — NTU PE6201.
