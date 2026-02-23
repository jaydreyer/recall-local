Your previous response failed schema validation.

Meeting title:
{{MEETING_TITLE}}

Transcript:
{{TRANSCRIPT}}

Previous response:
{{PREVIOUS_RESPONSE}}

Validation errors:
{{VALIDATION_ERRORS}}

Return strict JSON only (no markdown, no code fences) with exactly these fields:
- meeting_title (string, non-empty)
- summary (string, non-empty)
- decisions (array of strings)
- action_items (array of objects with non-empty owner, due_date, description)
- risks (array of strings)
- follow_ups (array of strings)

Use "unspecified" for unknown owner/due_date/details. Do not omit required keys.
