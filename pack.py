import json
import re
from groq import Groq
import prompts

LEADER_MODEL = "openai/gpt-oss-120b"   # Alpha and Omega
PACK_MODEL = "openai/gpt-oss-20b"      # Gamma specialists and verifier
GUARD_MODEL = "meta-llama/llama-prompt-guard-2-86m"  # Beta

BLOCKED_PATTERNS = [
    r"ignore (all|previous|your) (instructions|rules)",
    r"reveal (your|the) system prompt",
    r"api[_ ]?key",
]


class AlphexPack:
    def __init__(self, api_key):
        self.client = Groq(api_key=api_key)
        self.log = []  # shows which wolf did what

    def _chat(self, model, system, user, json_mode=False, max_tokens=600):
        args = dict(
            model=model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        if json_mode:
            args["response_format"] = {"type": "json_object"}
        reply = self.client.chat.completions.create(**args)
        return reply.choices[0].message.content.strip()

    # ---------- BETA: bodyguard ----------
    def beta_input_guard(self, text):
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False, "Blocked by Beta rules"
        try:
            reply = self.client.chat.completions.create(
                model=GUARD_MODEL,
                messages=[{"role": "user", "content": text}],
            )
            score = float(reply.choices[0].message.content.strip())
            if score > 0.8:
                return False, f"Blocked by Beta guard model (risk {score:.2f})"
        except Exception:
            pass  # if the guard model is unavailable, rules still protect us
        return True, "Passed"

    def beta_output_guard(self, text):
        if re.search(r"gsk_[A-Za-z0-9]{10,}", text):  # never leak Groq keys
            return "Beta removed this answer because it contained a secret."
        return text

    # ---------- ALPHA: leader ----------
    def alpha_route(self, text):
        raw = self._chat(LEADER_MODEL, prompts.ALPHA_ROUTER, text,
                         json_mode=True, max_tokens=150)
        try:
            plan = json.loads(raw)
        except json.JSONDecodeError:
            plan = {}
        if plan.get("specialist") not in prompts.GAMMA:
            plan["specialist"] = "planner_wolf"
        return plan

    # ---------- the full hunt ----------
    def run(self, text):
        self.log = []
        ok, why = self.beta_input_guard(text)
        self.log.append(f"Beta (input): {why}")
        if not ok:
            return "Alphex cannot help with that request.", self.log

        plan = self.alpha_route(text)
        wolf = plan["specialist"]
        self.log.append(f"Alpha: chose {wolf} ({plan.get('reason', 'no reason given')})")

        draft = self._chat(PACK_MODEL, prompts.GAMMA[wolf], text)
        self.log.append(f"Gamma: {wolf} wrote a draft")

        final = draft
        if plan.get("needs_verification", True):
            check_raw = self._chat(
                PACK_MODEL, prompts.VERIFIER,
                f"QUESTION:\n{text}\n\nDRAFT:\n{draft}",
                json_mode=True, max_tokens=200)
            try:
                check = json.loads(check_raw)
            except json.JSONDecodeError:
                check = {"approved": True, "problems": "verifier output unreadable"}
            self.log.append(f"Gamma Verifier: approved={check.get('approved')}")

            if not check.get("approved", True):
                final = self._chat(
                    LEADER_MODEL, prompts.OMEGA,
                    f"QUESTION:\n{text}\n\nDRAFT:\n{draft}\n\nOBJECTIONS:\n{check.get('problems')}")
                self.log.append("Omega: resolved the conflict")

        final = self.beta_output_guard(final)
        self.log.append("Beta (output): final check done")
        return final, self.log
