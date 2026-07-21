/**
 * Centralized API client for ShikhonAI backend
 * Handles authentication, error handling, and token management
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

class APIError extends Error {
  constructor(
    public status: number,
    public message: string,
    public data?: any
  ) {
    super(message);
    this.name = "APIError";
  }
}

/**
 * Get the JWT token from localStorage
 */
function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

/**
 * Set the JWT token in localStorage
 */
function setToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("access_token", token);
}

/**
 * Clear the JWT token from localStorage
 */
function clearToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("access_token");
}

/**
 * Generic fetch wrapper with authentication and error handling
 */
async function fetchAPI<T>(
  endpoint: string,
  options: RequestInit & { isFormData?: boolean } = {}
): Promise<T> {
  const url = `${BACKEND_URL}${endpoint}`;
  const token = getToken();

  const headers: HeadersInit = {
    ...(options.headers || {}),
  };

  // Add authorization header if token exists
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Don't set Content-Type for FormData (browser will set it automatically)
  if (!options.isFormData && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // Handle 401 Unauthorized - redirect to login
  if (response.status === 401) {
    clearToken();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new APIError(401, "Unauthorized - redirecting to login");
  }

  const data = await response.json();

  if (!response.ok) {
    throw new APIError(response.status, data.detail || "API request failed", data);
  }

  return data;
}

/**
 * Authentication APIs
 */
export const authAPI = {
  register: (payload: {
    email: string;
    password: string;
    name: string;
    role: "teacher" | "student";
  }) =>
    fetchAPI("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  login: (payload: { email: string; password: string }) =>
    fetchAPI("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getProfile: () => fetchAPI("/auth/me", { method: "GET" }),
};

/**
 * Exam APIs
 */
export const examAPI = {
  create: (payload: {
    title: string;
    subject: string;
    grade_level: string;
    duration_minutes: number;
  }) =>
    fetchAPI("/exams/create", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  get: (examId: string) => fetchAPI(`/exams/${examId}`, { method: "GET" }),

  activate: (examId: string) =>
    fetchAPI(`/exams/${examId}/activate`, { method: "POST" }),

  end: (examId: string) => fetchAPI(`/exams/${examId}/end`, { method: "POST" }),

  join: (examCode: string) =>
    fetchAPI(`/exams/join/${examCode}`, { method: "GET" }),
};

/**
 * Document APIs
 */
export const documentAPI = {
  upload: (formData: FormData) =>
    fetchAPI("/documents/upload", {
      method: "POST",
      body: formData,
      isFormData: true,
    }),

  list: () => fetchAPI("/documents/", { method: "GET" }),

  getStatus: (docId: string) =>
    fetchAPI(`/documents/${docId}/status`, { method: "GET" }),
};

/**
 * Session APIs
 */
export const sessionAPI = {
  submit: (sessionId: string, answers: any) =>
    fetchAPI(`/sessions/${sessionId}/submit`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),

  getResults: (sessionId: string) =>
    fetchAPI(`/sessions/${sessionId}/results`, { method: "GET" }),
};

/**
 * Analytics APIs
 */
export const analyticsAPI = {
  getExamAnalytics: (examId: string) =>
    fetchAPI(`/analytics/exam/${examId}`, { method: "GET" }),

  overrideScore: (answerId: string, overrideScore: number) =>
    fetchAPI(`/analytics/answers/${answerId}/override`, {
      method: "PUT",
      body: JSON.stringify({ override_score: overrideScore }),
    }),
};

/**
 * Question APIs
 */
export const questionAPI = {
  generate: (payload: {
    subject: string;
    grade_level: string;
    question_type: string;
    num_questions: number;
    marks_per_question: number;
    chapter_filter?: string;
    documents?: string[];
  }) =>
    fetchAPI("/questions/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

// Export token utilities for use in other modules
export { getToken, setToken, clearToken, APIError };
