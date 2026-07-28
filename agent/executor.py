import re
import sys
import threading
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Callable

from agent.planner       import create_plan, replan
from agent.error_handler import analyze_error, generate_fix, ErrorDecision


from core.config import get_gemini_client
from core.ai_router import get_ai_router

def _run_generated_code(description: str, speak: Callable | None = None) -> str:
    from google.genai import types

    client = get_gemini_client()

    if speak:
        speak("Writing custom code for this task, sir.")

    home      = Path.home()
    desktop   = home / "Desktop"
    downloads = home / "Downloads"
    documents = home / "Documents"

    if not desktop.exists():
        try:
            import winreg
            key     = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
            desktop = Path(winreg.QueryValueEx(key, "Desktop")[0])
        except Exception:
            pass

    client = get_gemini_client()

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are an expert Python developer. "
                    "Write clean, complete, working Python code. "
                    "Use standard library + common packages. "
                    "Install missing packages with subprocess + pip if needed. "
                    "Return ONLY the Python code. No explanation, no markdown, no backticks.\n\n"
                    f"SYSTEM PATHS:\n"
                    f"  Desktop   = r'{desktop}'\n"
                    f"  Downloads = r'{downloads}'\n"
                    f"  Documents = r'{documents}'\n"
                    f"  Home      = r'{home}'\n"
                )
            ),
            contents=f"Write Python code to accomplish this task:\n\n{description}"
        )
        code = (response.text or "").strip()
        code = re.sub(r"```(?:python)?", "", code).strip().rstrip("`").strip()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        print(f"[Executor] 🐍 Running generated code: {tmp_path}")

        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True, text=True,
            timeout=120, cwd=str(Path.home())
        )

        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        output = result.stdout.strip()
        error  = result.stderr.strip()

        if result.returncode == 0 and output:
            return output
        elif result.returncode == 0:
            return "Task completed successfully."
        elif error:
            raise RuntimeError(f"Code error: {error[:400]}")
        return "Completed."

    except subprocess.TimeoutExpired:
        raise RuntimeError("Generated code timed out after 120 seconds.")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Generated code failed: {e}")

def _inject_context(params: dict, tool: str, step_results: dict, goal: str = "") -> dict:
    if not step_results:
        return params

    params = dict(params)

    if tool == "file_controller" and params.get("action") in ("write", "create_file"):
        content = params.get("content", "")
        if not content or len(content) < 50:
            all_results = [
                v for v in step_results.values()
                if v and len(v) > 100 and v not in ("Done.", "Completed.")
            ]
            if all_results:
                combined = "\n\n---\n\n".join(all_results)
                translated = _translate_to_goal_language(combined, goal)
                params["content"] = translated
                print(f"[Executor] [OK] Injected + translated content")

    return params
def _translate_to_goal_language(content: str, goal: str) -> str:
    if not goal:
        return content
    try:
        client = get_gemini_client()
        print(f"[Executor] [LANG] Translating to language of: {goal[:50]}...")

        prompt = (
            f"You are a professional translator. First, determine the language of this user goal: '{goal}'. "
            f"Then, translate the following text into that exact language.\n"
            f"IMPORTANT:\n"
            f"- Translate EVERYTHING, leave nothing in English (unless the goal is English)\n"
            f"- Keep all facts, numbers, and data intact\n"
            f"- Keep the structure and formatting\n"
            f"- Output ONLY the translated text, nothing else. Do not output the name of the language.\n\n"
            f"Text to translate:\n{content[:4000]}"
        )
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        translated = (response.text or "").strip()
        print(f"[Executor] [OK] Translation done")
        return translated
    except Exception as e:
        print(f"[Executor] [FAIL] Translation failed: {e}")
        return content

def _call_tool(tool: str, parameters: dict, speak: Callable | None) -> str:
    if tool == "generated_code":
        description = parameters.get("description", "")
        if not description:
            raise ValueError("generated_code requires a 'description' parameter.")
        return _run_generated_code(description, speak=speak)

    from core.tool_registry import get_tool_callable
    func = get_tool_callable(tool)
    if func:
        # Some tools accept speak, others don't.
        import inspect
        sig = inspect.signature(func)
        from typing import Any
        kwargs: dict[str, Any] = {"parameters": parameters, "player": None}
        if "speak" in sig.parameters:
            kwargs["speak"] = speak
            
        result = func(**kwargs)
        return result or "Done."

    print(f"[Executor] [ERROR] Unknown tool '{tool}'")
    raise ValueError(f"Unknown tool '{tool}'")

class AgentExecutor:

    MAX_REPLAN_ATTEMPTS = 2

    def execute(
        self,
        goal:        str,
        speak:       Callable | None        = None,
        cancel_flag: threading.Event | None = None,
    ) -> str:
        safe_goal = goal.encode('ascii', 'ignore').decode('ascii')
        print(f"\n[Executor] [GOAL] Goal: {safe_goal}")

        replan_attempts = 0
        completed_steps = []
        step_results    = {} 
        plan            = create_plan(goal)
        
        # Safeguard: Check for missing file_controller when save/write/store is in goal
        save_keywords = ["save", "write", "store"]
        if any(kw in goal.lower() for kw in save_keywords):
            has_save_step = any(s.get("tool") == "file_controller" for s in plan.get("steps", []))
            if not has_save_step:
                print("[Executor] [WARNING] Incomplete plan detected (missing save step). Regenerating...")
                if speak: speak("Incomplete plan detected. Regenerating.")
                # Force a replan with a very specific instruction
                plan = create_plan(goal, context="CRITICAL: The user wants to SAVE or WRITE results to a file. You MUST include a SEPARATE file_controller step for this.")

        while True:
            steps = plan.get("steps", [])

            if not steps:
                msg = "I couldn't create a valid plan for this task, sir."
                if speak: speak(msg)
                return msg

            success      = True
            failed_step  = None
            failed_error = ""

            for step in steps:
                if cancel_flag and cancel_flag.is_set():
                    if speak: speak("Task cancelled, sir.")
                    return "Task cancelled."

                step_num = step.get("step", "?")
                tool     = step.get("tool", "generated_code")
                desc     = step.get("description", "")
                params   = step.get("parameters", {})

                params = _inject_context(params, tool, step_results, goal=goal)

                safe_desc = str(desc).encode('ascii', 'ignore').decode('ascii')
                print(f"\n[Executor] [STEP] Step {step_num}: [{tool}] {safe_desc}")

                attempt = 1
                step_ok = False

                while attempt <= 3:
                    if cancel_flag and cancel_flag.is_set():
                        break
                    try:
                        result = _call_tool(tool, params, speak)
                        
                        if step.get("critical", False):
                            router = get_ai_router()
                            verify_prompt = f"Goal: {desc}\nTool Output: {result}\nDid the tool output indicate success for the goal? Answer ONLY 'yes' or 'no'."
                            verify_res = router.generate(prompt=verify_prompt, system="You are a strict verification module.").strip().lower()
                            if "no" in verify_res:
                                raise Exception(f"Result verification failed. Output did not satisfy the goal: {result}")
                                
                        step_results[step_num] = result 
                        completed_steps.append(step)
                        safe_res = result[:100].encode('ascii', 'ignore').decode('ascii')
                        print(f"[Executor] [OK] Step {step_num} done: {safe_res}")
                        step_ok = True
                        break

                    except Exception as e:
                        error_msg = str(e)
                        safe_err = error_msg.encode('ascii', 'ignore').decode('ascii')
                        print(f"[Executor] [FAIL] Step {step_num} attempt {attempt} failed: {safe_err}")

                        recovery = analyze_error(step, error_msg, attempt=attempt)
                        decision = recovery["decision"]
                        user_msg = recovery.get("user_message", "")

                        if speak and user_msg:
                            speak(user_msg)

                        if decision == ErrorDecision.RETRY:
                            attempt += 1
                            import time; time.sleep(2)
                            continue

                        elif decision == ErrorDecision.SKIP:
                            print(f"[Executor] [SKIP] Skipping step {step_num}")
                            completed_steps.append(step)
                            step_ok = True
                            break

                        elif decision == ErrorDecision.ABORT:
                            msg = f"Task aborted, sir. {recovery.get('reason', '')}"
                            if speak: speak(msg)
                            return msg

                        else: 
                            fix_suggestion = recovery.get("fix_suggestion", "")
                            if fix_suggestion and tool != "generated_code":
                                try:
                                    fixed_step = generate_fix(step, error_msg, fix_suggestion)
                                    if speak: speak("Sir, I'm writing a custom script to handle this — reviewing it before running.")
                                    res = _call_tool(
                                        fixed_step["tool"],
                                        fixed_step["parameters"],
                                        speak
                                    )
                                    step_results[step_num] = res
                                    completed_steps.append(step)
                                    step_ok = True
                                    break
                                except Exception as fix_err:
                                    print(f"[Executor] [FAIL] Fix failed: {fix_err}")

                            failed_step  = step
                            failed_error = error_msg
                            success      = False
                            break

                if not step_ok and not failed_step:
                    failed_step  = step
                    failed_error = "Max retries exceeded"
                    success      = False

                if not success:
                    break

            if success:
                return self._summarize(goal, completed_steps, speak)

            if replan_attempts >= self.MAX_REPLAN_ATTEMPTS:
                msg = f"Task failed after {replan_attempts} replan attempts, sir."
                if speak: speak(msg)
                return msg

            if speak: speak("Adjusting my approach, sir.")

            replan_attempts += 1
            plan = replan(goal, completed_steps, failed_step or {}, failed_error)

    def _summarize(self, goal: str, completed_steps: list, speak: Callable | None) -> str:
        fallback = f"All done, sir. Completed {len(completed_steps)} steps for: {goal[:60]}."
        try:
            client = get_gemini_client()
            steps_str = "\n".join(f"- {s.get('description', '')}" for s in completed_steps)
            prompt    = (
                f'User goal: "{goal}"\n'
                f"Completed steps:\n{steps_str}\n\n"
                "Write a single natural sentence summarizing what was accomplished. "
                "Address the user as 'sir'. Be direct and positive."
            )
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            summary  = (response.text or "").strip()
            if speak: speak(summary)
            return summary
        except Exception:
            if speak: speak(fallback)
            return fallback
