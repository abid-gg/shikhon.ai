-- ShikhonAI — Supabase PostgreSQL schema (pgvector + RLS)
-- Run in Supabase SQL Editor or via migration tooling.

-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

CREATE TABLE public.users (
  id UUID PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('teacher', 'student')),
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE public.documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  teacher_id UUID NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  subject TEXT NOT NULL,
  grade_level TEXT NOT NULL CHECK (grade_level IN ('SSC', 'HSC')),
  upload_status TEXT NOT NULL DEFAULT 'pending'
    CHECK (upload_status IN ('pending', 'processing', 'done', 'failed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 768 dims: sentence-transformers/paraphrase-multilingual-mpnet-base-v2
CREATE TABLE public.chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID NOT NULL REFERENCES public.documents (id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  subject TEXT NOT NULL,
  chapter TEXT,
  page_number INT,
  content_type TEXT NOT NULL DEFAULT 'prose'
    CHECK (content_type IN ('prose', 'formula', 'table', 'caption')),
  embedding vector(768),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE public.board_questions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subject TEXT NOT NULL,
  grade_level TEXT NOT NULL CHECK (grade_level IN ('SSC', 'HSC')),
  bloom_level TEXT NOT NULL
    CHECK (bloom_level IN ('remember', 'understand', 'apply', 'analyze', 'evaluate')),
  question_type TEXT NOT NULL CHECK (question_type IN ('mcq', 'short', 'creative')),
  marks INT NOT NULL,
  source_year INT,
  question_text TEXT NOT NULL
);

CREATE TABLE public.exams (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  teacher_id UUID NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  subject TEXT NOT NULL,
  grade_level TEXT NOT NULL CHECK (grade_level IN ('SSC', 'HSC')),
  exam_code VARCHAR(8) NOT NULL UNIQUE,
  duration_minutes INT NOT NULL DEFAULT 60,
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'ended')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE public.exam_questions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_id UUID NOT NULL REFERENCES public.exams (id) ON DELETE CASCADE,
  question_text TEXT NOT NULL,
  question_type TEXT NOT NULL CHECK (question_type IN ('mcq', 'short', 'creative')),
  bloom_level TEXT NOT NULL
    CHECK (bloom_level IN ('remember', 'understand', 'apply', 'analyze', 'evaluate')),
  marks INT NOT NULL,
  expected_answer_points JSONB,
  chunk_ids JSONB,
  question_order INT NOT NULL DEFAULT 0
);

CREATE TABLE public.exam_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_id UUID NOT NULL REFERENCES public.exams (id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  submitted_at TIMESTAMPTZ,
  total_score DOUBLE PRECISION,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'submitted', 'graded')),
  UNIQUE (exam_id, student_id)
);

CREATE TABLE public.student_answers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES public.exam_sessions (id) ON DELETE CASCADE,
  question_id UUID NOT NULL REFERENCES public.exam_questions (id) ON DELETE CASCADE,
  answer_text TEXT,
  ai_score DOUBLE PRECISION,
  ai_justification TEXT,
  teacher_override_score DOUBLE PRECISION,
  is_flagged BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (session_id, question_id)
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

CREATE INDEX documents_teacher_id_idx ON public.documents (teacher_id);
CREATE INDEX chunks_document_id_idx ON public.chunks (document_id);
CREATE INDEX exams_teacher_id_idx ON public.exams (teacher_id);
CREATE INDEX exams_exam_code_idx ON public.exams (exam_code);
CREATE INDEX exam_questions_exam_id_idx ON public.exam_questions (exam_id);
CREATE INDEX exam_sessions_exam_id_idx ON public.exam_sessions (exam_id);
CREATE INDEX exam_sessions_student_id_idx ON public.exam_sessions (student_id);
CREATE INDEX student_answers_session_id_idx ON public.student_answers (session_id);

CREATE INDEX chunks_embedding_hnsw_idx ON public.chunks
  USING hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.board_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.exams ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.exam_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.exam_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.student_answers ENABLE ROW LEVEL SECURITY;

-- Helper: current app role from profile
CREATE OR REPLACE FUNCTION public.current_user_role()
RETURNS TEXT
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT role FROM public.users WHERE id = auth.uid();
$$;

CREATE OR REPLACE FUNCTION public.is_teacher()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.users u
    WHERE u.id = auth.uid() AND u.role = 'teacher'
  );
$$;

CREATE OR REPLACE FUNCTION public.is_student()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.users u
    WHERE u.id = auth.uid() AND u.role = 'student'
  );
$$;

CREATE OR REPLACE FUNCTION public.student_enrolled_in_exam(p_exam_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.exam_sessions es
    WHERE es.exam_id = p_exam_id AND es.student_id = auth.uid()
  );
$$;

CREATE OR REPLACE FUNCTION public.teacher_owns_exam(p_exam_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.exams e
    WHERE e.id = p_exam_id AND e.teacher_id = auth.uid()
  );
$$;

-- users
CREATE POLICY users_select_self ON public.users
  FOR SELECT USING (id = auth.uid());

CREATE POLICY users_update_self ON public.users
  FOR UPDATE USING (id = auth.uid()) WITH CHECK (id = auth.uid());

CREATE POLICY users_insert_self ON public.users
  FOR INSERT WITH CHECK (id = auth.uid());

-- documents: teachers only their rows
CREATE POLICY documents_teacher_all ON public.documents
  FOR ALL USING (teacher_id = auth.uid() AND public.is_teacher())
  WITH CHECK (teacher_id = auth.uid() AND public.is_teacher());

-- chunks: only teacher who owns the parent document
CREATE POLICY chunks_teacher_via_document ON public.chunks
  FOR ALL USING (
    public.is_teacher()
    AND EXISTS (
      SELECT 1 FROM public.documents d
      WHERE d.id = chunks.document_id AND d.teacher_id = auth.uid()
    )
  )
  WITH CHECK (
    public.is_teacher()
    AND EXISTS (
      SELECT 1 FROM public.documents d
      WHERE d.id = chunks.document_id AND d.teacher_id = auth.uid()
    )
  );

-- board_questions: readable by any signed-in user (curriculum / exam generation)
CREATE POLICY board_questions_select_auth ON public.board_questions
  FOR SELECT TO authenticated USING (true);

CREATE POLICY board_questions_teacher_write ON public.board_questions
  FOR ALL USING (public.is_teacher()) WITH CHECK (public.is_teacher());

-- exams: teachers own rows; students see active exams they joined (enrolled)
CREATE POLICY exams_teacher_all ON public.exams
  FOR ALL USING (teacher_id = auth.uid() AND public.is_teacher())
  WITH CHECK (teacher_id = auth.uid() AND public.is_teacher());

CREATE POLICY exams_student_select_enrolled_active ON public.exams
  FOR SELECT USING (
    public.is_student()
    AND status = 'active'
    AND public.student_enrolled_in_exam(id)
  );

-- exam_questions: teacher owns exam; enrolled student reads for that exam
CREATE POLICY exam_questions_teacher_all ON public.exam_questions
  FOR ALL USING (public.teacher_owns_exam(exam_id))
  WITH CHECK (public.teacher_owns_exam(exam_id));

CREATE POLICY exam_questions_student_select ON public.exam_questions
  FOR SELECT USING (
    public.is_student()
    AND public.student_enrolled_in_exam(exam_id)
    AND EXISTS (
      SELECT 1 FROM public.exams e
      WHERE e.id = exam_questions.exam_id AND e.status = 'active'
    )
  );

-- exam_sessions: student sees own; teacher sees sessions for their exams
CREATE POLICY exam_sessions_student_own ON public.exam_sessions
  FOR ALL USING (student_id = auth.uid() AND public.is_student())
  WITH CHECK (student_id = auth.uid() AND public.is_student());

CREATE POLICY exam_sessions_teacher_select ON public.exam_sessions
  FOR SELECT USING (
    public.is_teacher()
    AND public.teacher_owns_exam(exam_id)
  );

CREATE POLICY exam_sessions_teacher_update ON public.exam_sessions
  FOR UPDATE USING (
    public.is_teacher()
    AND public.teacher_owns_exam(exam_id)
  );

-- student_answers: student CRUD own via session; teacher read/update when owns exam
CREATE POLICY student_answers_student_all ON public.student_answers
  FOR ALL USING (
    public.is_student()
    AND EXISTS (
      SELECT 1 FROM public.exam_sessions es
      WHERE es.id = student_answers.session_id AND es.student_id = auth.uid()
    )
  )
  WITH CHECK (
    public.is_student()
    AND EXISTS (
      SELECT 1 FROM public.exam_sessions es
      WHERE es.id = student_answers.session_id AND es.student_id = auth.uid()
    )
  );

CREATE POLICY student_answers_teacher_select ON public.student_answers
  FOR SELECT USING (
    public.is_teacher()
    AND EXISTS (
      SELECT 1 FROM public.exam_sessions es
      JOIN public.exams e ON e.id = es.exam_id
      WHERE es.id = student_answers.session_id AND e.teacher_id = auth.uid()
    )
  );

CREATE POLICY student_answers_teacher_update ON public.student_answers
  FOR UPDATE USING (
    public.is_teacher()
    AND EXISTS (
      SELECT 1 FROM public.exam_sessions es
      JOIN public.exams e ON e.id = es.exam_id
      WHERE es.id = student_answers.session_id AND e.teacher_id = auth.uid()
    )
  );

-- ---------------------------------------------------------------------------
-- Auth hook: create public.users row on signup (email/password)
-- Configure in Supabase Dashboard → Authentication → Hooks, or run as SQL trigger
-- if you use a custom trigger on auth.users.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.users (id, email, role, name)
  VALUES (
    NEW.id,
    COALESCE(NEW.email, ''),
    COALESCE(NEW.raw_user_meta_data->>'role', 'student'),
    COALESCE(NEW.raw_user_meta_data->>'name', split_part(COALESCE(NEW.email, 'user'), '@', 1))
  );
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ---------------------------------------------------------------------------
-- Vector search RPC (used by backend services/retrieval.py)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.match_chunks_by_subject(
  query_embedding vector(768),
  filter_subject text,
  match_count int,
  chapter_filter text DEFAULT NULL
)
RETURNS TABLE (
  id uuid,
  document_id uuid,
  content text,
  subject text,
  chapter text,
  page_number int,
  content_type text,
  created_at timestamptz,
  similarity double precision
)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
  SELECT
    c.id,
    c.document_id,
    c.content,
    c.subject,
    c.chapter,
    c.page_number,
    c.content_type,
    c.created_at,
    (1 - (c.embedding <=> query_embedding))::double precision AS similarity
  FROM public.chunks c
  WHERE c.subject = filter_subject
    AND c.embedding IS NOT NULL
    AND (
      chapter_filter IS NULL
      OR trim(chapter_filter) = ''
      OR c.chapter ILIKE '%' || chapter_filter || '%'
    )
  ORDER BY c.embedding <=> query_embedding
  LIMIT match_count;
$$;

GRANT EXECUTE ON FUNCTION public.match_chunks_by_subject(vector(768), text, int, text)
  TO authenticated, service_role;
