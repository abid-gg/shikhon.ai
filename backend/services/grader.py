"""AI grading service using Gemini API."""

import json
import httpx
from typing import Optional


async def grade_session(
    session_id: str,
    supabase,
    gemini_api_key: str,
) -> None:
    """Grade all answers in a session using Gemini API."""
    
    try:
        # Fetch all student answers for this session
        answers_result = (
            supabase.table("student_answers")
            .select("*, exam_questions:question_id(*)")
            .eq("session_id", session_id)
            .execute()
        )
        
        total_score = 0
        
        for answer_record in answers_result.data:
            answer = answer_record
            question = answer["exam_questions"]
            
            # Build the prompt
            system_prompt = (
                "You are a Bangla subject teacher marking a student's exam answer. "
                "Return ONLY valid JSON."
            )
            
            user_prompt = f"""Question: {question['question_text']}
Total marks: {question['marks']}

Expected answer points (curriculum-grounded):
{format_expected_points(question.get('expected_answer_points', []))}

Student's answer:
{answer['answer_text']}

Mark the student's answer. For each expected point, check if the student addressed it.
Return JSON:
{{
  "score": <float, 0 to {question['marks']}>,
  "justification": "<1-2 sentences in Bangla explaining the score>",
  "points_addressed": [true/false for each expected point],
  "is_flagged": <true if answer is ambiguous and needs teacher review>
}}

Rules:
- Award partial marks if student addressed some points
- is_flagged = true if: answer is very short (<20 words) for a high-mark question, OR score is exactly at the boundary (50% of marks), OR answer language is unexpected
- Be fair to the student; give benefit of the doubt for correct ideas expressed differently"""
            
            # Call Gemini API
            score_data = await call_gemini(
                gemini_api_key,
                system_prompt,
                user_prompt,
            )
            
            # Update student_answers record
            supabase.table("student_answers").update({
                "ai_score": score_data.get("score", 0),
                "ai_justification": score_data.get("justification", ""),
                "is_flagged": score_data.get("is_flagged", False),
            }).eq("id", answer["id"]).execute()
            
            total_score += score_data.get("score", 0)
        
        # Update exam_session with total score and graded status
        supabase.table("exam_sessions").update({
            "total_score": total_score,
            "status": "graded",
        }).eq("id", session_id).execute()
        
    except Exception as e:
        print(f"Error grading session {session_id}: {e}")


async def call_gemini(api_key: str, system: str, user_message: str) -> dict:
    """Call Gemini API with message."""
    
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": user_message,
                    }
                ],
            }
        ],
        "systemInstruction": {
            "parts": [
                {
                    "text": system,
                }
            ]
        },
    }
    
    headers = {
        "Content-Type": "application/json",
    }
    
    params = {"key": api_key}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract the response text
            if data.get("candidates"):
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                # Try to parse as JSON
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    # If not valid JSON, return a safe default
                    return {
                        "score": 0,
                        "justification": "গ্রেডিং সিস্টেম ত্রুটি",
                        "points_addressed": [],
                        "is_flagged": True,
                    }
            
            return {
                "score": 0,
                "justification": "উত্তর পেতে ব্যর্থ",
                "points_addressed": [],
                "is_flagged": True,
            }
    
    except Exception as e:
        print(f"Gemini API error: {e}")
        return {
            "score": 0,
            "justification": f"API ত্রুটি: {str(e)[:50]}",
            "points_addressed": [],
            "is_flagged": True,
        }


def format_expected_points(points: Optional[list] | dict | None) -> str:
    """Format expected answer points for the prompt."""
    if not points:
        return "N/A"
    
    if isinstance(points, dict):
        points = points.get("points", [])
    
    if not isinstance(points, list):
        return str(points)
    
    return "\n".join(f"{i+1}. {p}" for i, p in enumerate(points))
