"""Small, optional OpenAI Responses API integration for the Study Coach."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


class StudyCoachUnavailable(Exception):
    """Raised when the configured AI provider cannot return a usable answer."""


def generate_study_coach_reply(*, mode, prompt, context):
    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    if not api_key:
        return None

    mode_instructions = {
        'ask': 'Explain the requested topic clearly, with a small example and one quick check question.',
        'plan': 'Create a practical, encouraging revision plan from the student’s actual deadlines. Keep it realistic.',
        'quiz': 'Create five useful practice questions from the provided material, followed by a separate answer key.',
    }
    payload = {
        'model': settings.OPENAI_MODEL,
        'store': False,
        'max_output_tokens': 700,
        'instructions': (
            'You are StudyMate, a kind and practical study coach. Help the student learn instead of doing '
            'graded work for them. Use simple language, short headings, and actionable steps. Use only the '
            'student context supplied below for personal schedule facts. If it is incomplete, say so briefly '
            'and do not invent deadlines or study material. Do not ask for personal identifying information. '
            + mode_instructions[mode]
        ),
        'input': (
            f"Student request: {prompt or 'Please help me prioritize and study effectively.'}\n\n"
            f"Study context (student-owned records): {json.dumps(context, ensure_ascii=False)}"
        ),
    }
    request = Request(
        'https://api.openai.com/v1/responses',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urlopen(request, timeout=25) as response:
            result = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        if exc.code == 401:
            message = 'The AI service rejected its API key. Check OPENAI_API_KEY.'
        elif exc.code == 429:
            message = 'The AI service is busy or its usage limit was reached. Try again later.'
        else:
            message = 'The AI service could not complete that request. Try again later.'
        raise StudyCoachUnavailable(message) from None
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise StudyCoachUnavailable(
            'The AI service could not be reached. Check your connection and try again.'
        ) from None

    text_parts = []
    for item in result.get('output', []):
        if item.get('type') != 'message':
            continue
        for content in item.get('content', []):
            if content.get('type') == 'output_text' and content.get('text'):
                text_parts.append(content['text'])
    reply = '\n'.join(text_parts).strip()
    if not reply:
        raise StudyCoachUnavailable('The AI service returned an empty reply. Please try again.')
    return reply
