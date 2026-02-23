Your previous response failed validation.

Validation errors:
{{VALIDATION_ERRORS}}

Previous response:
{{PREVIOUS_RESPONSE}}

Regenerate the answer using only the provided context.

Mandatory output requirements:
1. Return only valid JSON (no markdown, no code fences).
2. Use exactly this shape:
{
  "answer": "string",
  "citations": [{"doc_id": "string", "chunk_id": "string"}],
  "confidence_level": "low|medium|high",
  "assumptions": ["string"]
}
3. Every citation pair must exist in the context.
4. Do not include any citation that is not explicitly present in the context.
5. If query is not answerable from context, answer exactly:
   "I don't have enough information in the retrieved context to answer that."
   and set confidence_level to "low".

User query:
{{QUERY}}

Retrieved context:
{{CONTEXT}}
