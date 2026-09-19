import re
import os
from typing import Dict, Any, List, Tuple

# Pre-compiled Regex Patterns for Prompt Injection & Jailbreak attempts
PROMPT_INJECTION_PATTERNS = [
    r"(?i)\bignore\s+(all\s+)?(previous|prior|above|system)\s+(instructions|prompts|rules|guidelines)\b",
    r"(?i)\b(reveal|show|display|print|give)\s+(me\s+)?(your\s+)?(all\s+)?(hidden\s+|secret\s+)?(system\s+prompt|initial\s+prompt|developer\s+mode|internal\s+instructions|prompt|instructions)\b",
    r"(?i)\boverride\s+(system\s+)?(rules|safety|guidelines|controls|filters)\b",
    r"(?i)\b(pretend|act\s+as|roleplay\s+as)\s+(an\s+unrestricted|a\s+hacked|dan|jailbroken|god\s+mode)\b",
    r"(?i)\bdisregard\s+(all\s+)?(safety|rules|constraints|instructions)\b",
    r"(?i)\bforget\s+(all\s+)?(previous|prior)\s+(instructions|context)\b",
    r"(?i)\byou\s+are\s+now\s+in\s+developer\s+mode\b",
    r"(?i)\bdo\s+anything\s+now\b",
    r"(?i)\b(system\s+prompt|hidden\s+prompt)\b",
    r"(?i)\bbypass\s+(guardrails|filters|content\s+policy)\b",
]

JAILBREAK_KEYWORDS = [
    "dan mode", "developer mode", "jailbreak", "unfiltered mode",
    "always answer", "disable ethical guidelines", "exploit mode"
]

TOXICITY_PATTERNS = [
    r"(?i)\b(kill\s+yourself|die|hate\s+you|fuck|shit|bitch|bastard|idiot|moron)\b",
    r"(?i)\b(how\s+to\s+(sabotage|bomb|destroy|short-circuit|explode)\s+the\s+substation|grid)\b",
    r"(?i)\b(attack|blow\s+up|vandalize)\s+(the\s+)?(power\s+plant|grid|transformer)\b"
]

# Sensitive patterns (PII and credentials)
EMAIL_PATTERN = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
PHONE_PATTERN = r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
EMPLOYEE_ID_PATTERN = r"\b(?:EMP|GRID|TECH|OP)-[A-Z0-9]{4,8}\b"
ACCOUNT_ID_PATTERN = r"\b(?:ACCT|MTR|CUST)-[0-9]{5,10}\b"
SSN_PATTERN = r"\b\d{3}-\d{2}-\d{4}\b"
API_KEY_PATTERN = r"(?:gsk_[a-zA-Z0-9]{20,}|sk-[a-zA-Z0-9]{20,}|pcsk_[a-zA-Z0-9_-]{20,}|Bearer\s+[a-zA-Z0-9_.-]{30,})"


class GuardrailsResult:
    def __init__(
        self,
        is_safe: bool = True,
        status: str = "Safe",  # Safe, Suspicious, Blocked
        reason: str = "",
        sanitized_text: str = "",
        pii_detected: bool = False,
        injection_detected: bool = False,
        toxic_detected: bool = False,
        data_leakage_detected: bool = False,
    ):
        self.is_safe = is_safe
        self.status = status
        self.reason = reason
        self.sanitized_text = sanitized_text
        self.pii_detected = pii_detected
        self.injection_detected = injection_detected
        self.toxic_detected = toxic_detected
        self.data_leakage_detected = data_leakage_detected

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "status": self.status,
            "reason": self.reason,
            "sanitized_text": self.sanitized_text,
            "pii_detected": self.pii_detected,
            "injection_detected": self.injection_detected,
            "toxic_detected": self.toxic_detected,
            "data_leakage_detected": self.data_leakage_detected,
        }


class GuardrailsManager:
    """Enterprise AI Guardrails suite for GridKnowledge."""

    def __init__(self):
        self.min_length = int(os.getenv("MIN_QUERY_LENGTH", "2"))
        self.max_length = int(os.getenv("MAX_QUERY_LENGTH", "1000"))

    def validate_input(self, query: str) -> GuardrailsResult:
        """Run all input checks in sequence: Length -> Toxicity -> Injection -> Jailbreak -> PII Masking."""
        if not query or not query.strip():
            return GuardrailsResult(
                is_safe=False,
                status="Blocked",
                reason="Query cannot be empty.",
                sanitized_text="",
            )

        trimmed = query.strip()

        # 1. Length validation
        if len(trimmed) < self.min_length:
            return GuardrailsResult(
                is_safe=False,
                status="Blocked",
                reason=f"Query is too short. Minimum length is {self.min_length} characters.",
                sanitized_text=trimmed,
            )

        if len(trimmed) > self.max_length:
            return GuardrailsResult(
                is_safe=False,
                status="Blocked",
                reason=f"Query exceeds maximum allowed length of {self.max_length} characters.",
                sanitized_text=trimmed[:self.max_length],
            )

        # 2. Toxic content / Sabotage detection
        for pattern in TOXICITY_PATTERNS:
            if re.search(pattern, trimmed):
                return GuardrailsResult(
                    is_safe=False,
                    status="Blocked",
                    reason="Inappropriate or hazardous content detected. Request blocked by safety policy.",
                    sanitized_text=trimmed,
                    toxic_detected=True,
                )

        # 3. Prompt injection detection
        for pattern in PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, trimmed):
                return GuardrailsResult(
                    is_safe=False,
                    status="Blocked",
                    reason="Prompt injection pattern detected. Queries attempting to override instructions are prohibited.",
                    sanitized_text=trimmed,
                    injection_detected=True,
                )

        # 4. Jailbreak keyword detection
        lowered = trimmed.lower()
        for jb in JAILBREAK_KEYWORDS:
            if jb in lowered:
                return GuardrailsResult(
                    is_safe=False,
                    status="Blocked",
                    reason="Jailbreak signature detected. Request blocked by security controls.",
                    sanitized_text=trimmed,
                    injection_detected=True,
                )

        # 5. PII Detection and Masking
        sanitized_query, pii_found = self.mask_pii(trimmed)

        # Determine status: Suspicious if multiple punctuation/delimiter tricks or minor anomalies
        status = "Safe"
        if pii_found:
            status = "Suspicious"  # Allowed through, but flagged for PII masking

        return GuardrailsResult(
            is_safe=True,
            status=status,
            reason="Input validation passed.",
            sanitized_text=sanitized_query,
            pii_detected=pii_found,
        )

    def mask_pii(self, text: str) -> Tuple[str, bool]:
        """Detect and redact sensitive personal identifiers with domain labels."""
        found = False
        masked = text

        # Redact emails
        if re.search(EMAIL_PATTERN, masked):
            masked = re.sub(EMAIL_PATTERN, "[REDACTED_EMAIL]", masked)
            found = True

        # Redact phone numbers
        if re.search(PHONE_PATTERN, masked):
            masked = re.sub(PHONE_PATTERN, "[REDACTED_PHONE]", masked)
            found = True

        # Redact employee IDs
        if re.search(EMPLOYEE_ID_PATTERN, masked):
            masked = re.sub(EMPLOYEE_ID_PATTERN, "[REDACTED_EMP_ID]", masked)
            found = True

        # Redact customer/meter IDs
        if re.search(ACCOUNT_ID_PATTERN, masked):
            masked = re.sub(ACCOUNT_ID_PATTERN, "[REDACTED_ACCOUNT_ID]", masked)
            found = True

        # Redact SSN/National IDs
        if re.search(SSN_PATTERN, masked):
            masked = re.sub(SSN_PATTERN, "[REDACTED_SSN]", masked)
            found = True

        return masked, found

    def validate_output(
        self, response_text: str, retrieved_contexts: List[Dict[str, Any]]
    ) -> GuardrailsResult:
        """Validate LLM output for data leakage, grounding, and credential exposure."""
        if not response_text:
            return GuardrailsResult(
                is_safe=False,
                status="Blocked",
                reason="Response is empty.",
                sanitized_text="",
            )

        sanitized_response = response_text

        # 1. Data leakage check (API keys, secrets, tokens)
        if re.search(API_KEY_PATTERN, sanitized_response):
            sanitized_response = re.sub(API_KEY_PATTERN, "[REDACTED_SECRET]", sanitized_response)
            return GuardrailsResult(
                is_safe=False,
                status="Blocked",
                reason="Data leakage prevented: secret key detected in model response.",
                sanitized_text="A security restriction prevented rendering this output.",
                data_leakage_detected=True,
            )

        # 2. Output PII check & sanitization
        sanitized_response, pii_found = self.mask_pii(sanitized_response)

        # 3. Grounding validation: If model claims it has no info, verify that's acceptable
        insufficient_phrase = "couldn't find sufficient information"
        is_insufficient = insufficient_phrase in sanitized_response.lower()

        # If retrieved context was empty, response MUST declare insufficient information
        if not retrieved_contexts and not is_insufficient:
            sanitized_response = "I couldn't find sufficient information in the available grid documentation."

        return GuardrailsResult(
            is_safe=True,
            status="Safe",
            reason="Output validation passed.",
            sanitized_text=sanitized_response,
            pii_detected=pii_found,
        )

    def isolate_document_context(self, text: str) -> str:
        """Wrap document text in untrusted tags to prevent prompt injection via knowledge base documents."""
        # Clean any existing xml/tag exploits
        cleaned = text.replace("<script>", "").replace("</script>", "")
        return f"<context_document>\n{cleaned}\n</context_document>"


# Global singleton instance
guardrails = GuardrailsManager()
