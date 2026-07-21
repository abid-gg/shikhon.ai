# ShikhonAI

Full-stack scaffold for **ShikhonAI** — a Bangla curriculum-aware RAG exam platform for SSC/HSC students in Bangladesh.

## Layout

| Path | Stack |
|------|--------|
| `frontend/` | Next.js 14 (App Router), Tailwind CSS, shadcn/ui — deploy on **Vercel** (free tier). |
| `backend/` | FastAPI — deploy on **Render** (free tier). |
| `pipeline/` | Standalone Python scripts for PDF → chunks + embeddings (local `sentence-transformers`). |

## Environment variables

Copy each `.env.example` to `.env` / `.env.local` and fill in values from the Supabase dashboard and your LLM provider.

- **Backend:** `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GEMINI_API_KEY`, `FRONTEND_URL`
- **Frontend:** `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_BACKEND_URL`

## Database

1. Create a Supabase project and enable **pgvector** (the schema runs `CREATE EXTENSION IF NOT EXISTS vector;`).
2. Run `backend/schema.sql` in the SQL Editor.
3. Configure **Auth** (email/password). New users get a `public.users` row from the `on_auth_user_created` trigger; pass `role` (`teacher` or `student`) and `name` in `raw_user_meta_data` at signup so the trigger satisfies the `role` check constraint.

**Student exam join:** RLS allows students to read **active** exams only after an `exam_sessions` row exists. Resolve `exam_code` and create the session using the **service role** on the backend (or an Edge Function), then the client can load the exam with the user JWT.

## Local development

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

**Backend**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Set `FRONTEND_URL=http://localhost:3000` for CORS.

## Pipeline

The `pipeline/` directory contains the research tooling for Bangla PDF ingestion, chunking, embedding, and retrieval benchmarking.

- `pipeline/retrieval_benchmark.py`: benchmark embedding models with a golden Q&A dataset and a corpus of chunks.
  - Models included: `paraphrase-multilingual-mpnet-base-v2`, `intfloat/multilingual-e5-large`, `l3cube-pune/bengali-sentence-bert-nli`, and OpenAI `text-embedding-3-small` when `OPENAI_API_KEY` is available.
  - Produces `pipeline/benchmark_results.json` and prints a results table.
- `pipeline/create_golden_dataset.py`: interactive CLI to build a manual golden dataset from Supabase chunks.
  - Uses `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` from environment variables.
  - Saves collected Q&A examples to `pipeline/golden_dataset.json`.

Example pipeline usage:

```bash
cd pipeline
python ..\backend\venv\Scripts\python.exe retrieval_benchmark.py --golden golden_dataset.json --corpus corpus_chunks.json
python ..\backend\venv\Scripts\python.exe create_golden_dataset.py
```

If you prefer a separate environment for pipeline tools:

```bash
cd pipeline
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## API

- Root: `GET /`
- Health: `GET /health`
- OpenAPI: `/docs`
