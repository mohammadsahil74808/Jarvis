# agent/tool_executor.py

import asyncio
import traceback
import sys
from typing import Dict, Any

# We'll use lazy imports for genai and other heavy modules
_genai_cache = None

def _get_genai():
    global _genai_cache
    if _genai_cache is None:
        from google import genai
        from google.genai import types
        _genai_cache = (genai, types)
    return _genai_cache

class ToolExecutor:
    def __init__(self, jarvis):
        self.jarvis = jarvis
        
        # Fallback suggestions map
        self.FALLBACK_SUGGESTIONS = {
            "browser_control": "Sir, browser action failed. Maybe try 'computer_control' or 'cmd_control' as a fallback?",
            "open_app": "Sir, I couldn't open the app. Try using 'web_search' to find the app path or use 'cmd_control'.",
            "screen_process": "Sir, vision module failed. Is the screen content visible clearly?",
            "web_search": "Sir, search failed. I already tried fallback engines, but you might want to try 'browser_control' manually.",
            "file_manager": "Sir, file action failed. Check if the path is correct or use 'cmd_control' for direct disk access."
        }

    async def execute(self, fc) -> Any:
        name = fc.name
        # Re-route hallucinated names
        if name in ["file_controller", "file_brain"]:
            print(f"[JARVIS] Hallucinated tool {name} re-routed to file_manager")
            name = "file_manager"
            
        args = dict(fc.args or {})
        print(f"[JARVIS] [TOOL] {name}  {args}")
        
        self.jarvis.ui.set_state("THINKING")

        # Update Session Context
        self.jarvis.session_context["last_tool"] = name
        self.jarvis._config_dirty = True
        
        # Update last_app, last_query, etc.
        self._update_session_context(name, args)

        # Log usage tracker
        if self.jarvis.usage_tracker:
            if name == "open_app":
                self.jarvis.memory_executor.submit(self.jarvis.usage_tracker.log_event, "app", args.get("app_name", "Unknown"))
            elif name in ["web_search", "browser_control"]:
                 self.jarvis.memory_executor.submit(self.jarvis.usage_tracker.log_event, "command", name)

        loop = asyncio.get_running_loop()
        
        # Handle specific tools that have complex logic or different return patterns
        if name == "save_memory":
            return await self._handle_save_memory(fc, args)
        
        if name == "manage_plan":
            return await self._handle_manage_plan(fc, args)
            
        if name == "capture_screen_context":
            return await self._handle_capture_screen_context(fc, args)
            
        if name == "browser_agent":
            return await self._handle_browser_agent(fc, args, loop)
            
        if name == "generate_image":
            return await self._handle_generate_image(fc, args, loop)
            
        if name == "screen_vision":
            return await self._handle_screen_vision(fc, args, loop)
            
        if name == "recall_memory":
            return await self._handle_recall_memory(fc, args, loop)
            
        if name == "research_mode":
            return await self._handle_research_mode(fc, args, loop)
            
        if name == "shutdown_system":
            return await self._handle_shutdown_system(fc, args)

        # Standard tool execution with self-healing
        result = await self._execute_standard_tool(fc, name, args, loop)
        
        if not self.jarvis.ui.muted:
            self.jarvis.ui.set_state("LISTENING")

        print(f"[JARVIS] Tool Result: {name} -> {str(result)[:80]}")
        
        _, types = _get_genai()
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    def _update_session_context(self, name, args):
        if name == "open_app":
            self.jarvis.session_context["last_app"] = args.get("app_name")
            self.jarvis.session_context["last_action"] = "open_app"
        elif name == "web_search":
            self.jarvis.session_context["last_query"] = args.get("query")
            self.jarvis.session_context["last_action"] = "web_search"
        elif name == "file_manager":
            self.jarvis.session_context["last_file"] = args.get("path")
            self.jarvis.session_context["last_action"] = args.get("action")
        elif name == "browser_control":
            self.jarvis.session_context["last_query"] = args.get("query") or args.get("url")
            self.jarvis.session_context["last_action"] = args.get("action")
        elif name == "browser_agent":
            self.jarvis.session_context["last_query"] = args.get("query") or args.get("url")
            self.jarvis.session_context["last_action"] = args.get("action")
        elif name == "screen_vision":
            self.jarvis.session_context["last_action"] = args.get("action", "analyze")

    async def _handle_save_memory(self, fc, args):
        category = args.get("category", "notes")
        key      = args.get("key", "")
        value    = args.get("value", "")
        if key and value:
            from memory.memory_manager import update_memory
            update_memory({category: {key: {"value": value}}})
            print(f"[Memory] [SAVE] save_memory: {category}/{key} = {value}")
        
        if not self.jarvis.ui.muted:
            self.jarvis.ui.set_state("LISTENING")
            
        _, types = _get_genai()
        return types.FunctionResponse(
            id=fc.id, name=fc.name,
            response={"result": "ok", "silent": True}
        )

    async def _handle_manage_plan(self, fc, args):
        action = args.get("action", "create")
        result = "Done."
        if action == "create":
            steps = args.get("steps", [])
            self.jarvis.active_plan = [{"step": s, "done": False} for s in steps]
            self.jarvis.ui.write_log(f"SYS: New Project Plan Initialised ({len(steps)} steps)")
            for i, s in enumerate(steps, 1):
                self.jarvis.ui.write_log(f"PLAN: {i}. {s}")
            result = "Plan created successfully. Sir, now start with the first step."
        elif action == "update":
            index = args.get("index", 1) - 1
            if self.jarvis.active_plan and 0 <= index < len(self.jarvis.active_plan):
                self.jarvis.active_plan[index]["done"] = True
                step_text = self.jarvis.active_plan[index]["step"]
                self.jarvis.ui.write_log(f"PLAN: [DONE] {step_text}")
                result = f"Step {index+1} marked as done."
            else:
                result = "Invalid step index or no active plan."
        elif action == "clear":
            self.jarvis.active_plan = None
            self.jarvis.ui.write_log("SYS: Plan cleared.")
            result = "Plan cleared."
        
        if not self.jarvis.ui.muted:
            self.jarvis.ui.set_state("LISTENING")
            
        _, types = _get_genai()
        return types.FunctionResponse(
            id=fc.id, name=fc.name,
            response={"result": result}
        )

    async def _handle_capture_screen_context(self, fc, args):
        self.jarvis.ui.set_state("THINKING")
        loop = asyncio.get_running_loop()
        
        def _blocking_capture():
            from actions.screen_processor import _capture_screenshot
            from core.config import get_gemini_client
            try:
                img_bytes = _capture_screenshot()
                _, types = _get_genai()
                client = get_gemini_client()
                prompt = (
                    "Analyze this screenshot. Describe: 1. The active window. "
                    "2. Important buttons/text visible. 3. Their approximate coordinates (0-1000 scale, e.g. center is 500,500). "
                    "Be concise. Format as a bulleted list."
                )
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[
                        types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                        prompt
                    ]
                )
                return response.text.strip()
            except Exception as e:
                return f"Screen capture failed: {e}"

        try:
            self.jarvis.screen_context = await loop.run_in_executor(None, _blocking_capture)
            self.jarvis.ui.write_log("SYS: Screen state analyzed and updated.")
            result = f"Screen context updated: {self.jarvis.screen_context}"
        except Exception as e:
            result = f"Process failed: {e}"
        
        if not self.jarvis.ui.muted:
            self.jarvis.ui.set_state("LISTENING")
            
        _, types = _get_genai()
        return types.FunctionResponse(
            id=fc.id, name=fc.name,
            response={"result": result}
        )

    async def _handle_browser_agent(self, fc, args, loop):
        try:
            from actions.browser_agent import browser_agent
            result = await loop.run_in_executor(None, browser_agent, args)
        except Exception as e:
            result = f"Browser Agent failed: {e}"
        if not self.jarvis.ui.muted:
            self.jarvis.ui.set_state("LISTENING")
        _, types = _get_genai()
        return types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result})

    async def _handle_generate_image(self, fc, args, loop):
        try:
            from actions.image_generator import generate_image
            result = await loop.run_in_executor(None, generate_image, args, self.jarvis)
        except Exception as e:
            result = f"Image Generation failed: {e}"
        if not self.jarvis.ui.muted:
            self.jarvis.ui.set_state("LISTENING")
        _, types = _get_genai()
        return types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result})

    async def _handle_screen_vision(self, fc, args, loop):
        try:
            from actions.screen_vision import screen_vision
            result = await loop.run_in_executor(None, screen_vision, args)
        except Exception as e:
            result = f"Screen Vision failed: {e}"
        if not self.jarvis.ui.muted:
            self.jarvis.ui.set_state("LISTENING")
        _, types = _get_genai()
        return types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result})

    async def _handle_recall_memory(self, fc, args, loop):
        try:
            query = args.get("query")
            k = args.get("k", 5)
            from memory.semantic_memory import search_semantic_memory
            memories = await loop.run_in_executor(None, lambda: search_semantic_memory(query, k))
            if not memories:
                result = "No similar memories found, sir."
            else:
                formatted = []
                for m in memories:
                    formatted.append(f"[{m['timestamp']}] {m['text']}")
                result = "Found similar memories:\n" + "\n".join(formatted)
        except Exception as e:
            result = f"Recall failed: {e}"
        if not self.jarvis.ui.muted:
            self.jarvis.ui.set_state("LISTENING")
        _, types = _get_genai()
        return types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result})

    async def _handle_research_mode(self, fc, args, loop):
        from main import _WIDGETS_OK  # Note: Circular import might be an issue, we'll fix later if needed
        try:
            from ui.deep_research_widget import DeepResearchWidget
        except ImportError:
            _WIDGETS_OK = False
            
        _rw = None
        if _WIDGETS_OK:
            try:
                _rw = DeepResearchWidget.launch(
                    self.jarvis.ui.root, args.get("query", ""))
            except Exception as _e:
                print(f"[Widget] {_e}")
        try:
            from actions.research_mode import research_mode
            result = await loop.run_in_executor(None, research_mode, args)
        except Exception as e:
            result = f"Research Mode failed: {e}"
        if _rw:
            self.jarvis.ui.root.after(0, lambda r=result: _rw.show_done(r))
        if not self.jarvis.ui.muted:
            self.jarvis.ui.set_state("LISTENING")
        _, types = _get_genai()
        return types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result})

    async def _handle_shutdown_system(self, fc, args):
        confirm = args.get("confirm", False)
        if confirm:
            self.jarvis.ui.write_log("SYS: Shutdown initiated via LLM command.")
            # Trigger clean exit after turn finishes
            # We use after() to let the speaker finish the current turn
            self.jarvis.ui.root.after(5000, self.jarvis.ui.root.destroy)
            result = "System is shutting down. Goodbye, Sahil."
        else:
            result = "Shutdown canceled (confirmation required)."
            
        if not self.jarvis.ui.muted:
            self.jarvis.ui.set_state("LISTENING")
        _, types = _get_genai()
        return types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result})

    async def _execute_standard_tool(self, fc, name, args, loop):
        from main import _WIDGETS_OK
        try:
            from ui.file_search_widget import FileSearchWidget
            from ui.web_search_widget import WebSearchWidget
        except ImportError:
            _WIDGETS_OK = False

        result = "Done."
        attempts = 0
        max_attempts = 2
        while attempts < max_attempts:
            try:
                if name == "open_app":
                    from actions.open_app import open_app
                    r = await loop.run_in_executor(None, lambda: open_app(parameters=args, response=None, player=self.jarvis.ui))
                    result = r or f"Opened {args.get('app_name')}."
                    break

                elif name == "weather_report":
                    from actions.weather_report import weather_action
                    r = await loop.run_in_executor(None, lambda: weather_action(parameters=args, player=self.jarvis.ui))
                    result = r or "Weather delivered."
                    break

                elif name == "browser_control":
                    from actions.browser_control import browser_control
                    r = await loop.run_in_executor(None, lambda: browser_control(parameters=args, player=self.jarvis.ui))
                    result = r or "Done."
                    break

                elif name == "file_manager":
                    from actions.file_manager import file_manager
                    _fmw = None
                    _fm_act = args.get("action", "")
                    if _WIDGETS_OK and _fm_act in ("find", "search", "deep_search"):
                        _fm_q = args.get("query") or args.get("name") or ""
                        try:
                            _fmw = FileSearchWidget.launch(
                                self.jarvis.ui.root, _fm_q, _fm_act)
                        except Exception as _e:
                            print(f"[Widget] {_e}")
                    r = await loop.run_in_executor(
                        None, lambda: file_manager(parameters=args, player=self.jarvis.ui))
                    result = r or "Done."
                    if _fmw:
                        self.jarvis.ui.root.after(0, lambda r=result: _fmw.show_results(r))
                    break

                elif name == "send_message":
                    from actions.send_message import send_message
                    r = await loop.run_in_executor(None, lambda: send_message(parameters=args, response=None, player=self.jarvis.ui, session_memory=None))
                    result = r or f"Message sent to {args.get('receiver')}."
                    break

                elif name == "reminder":
                    from actions.reminder import reminder
                    r = await loop.run_in_executor(None, lambda: reminder(parameters=args, response=None, player=self.jarvis.ui))
                    result = r or "Reminder set."
                    break

                elif name == "youtube_video":
                    from actions.youtube_video import youtube_video
                    r = await loop.run_in_executor(None, lambda: youtube_video(parameters=args, response=None, player=self.jarvis.ui))
                    result = r or "Done."
                    break

                elif name == "screen_process":
                    from actions.screen_processor import screen_process
                    r = await loop.run_in_executor(
                        None,
                        lambda: screen_process(parameters=args, response=None, player=self.jarvis.ui, session_memory=None)
                    )
                    result = "Vision module activated. Stay completely silent — vision module will speak directly."
                    break

                elif name == "computer_settings":
                    from actions.computer_settings import computer_settings
                    r = await loop.run_in_executor(None, lambda: computer_settings(parameters=args, response=None, player=self.jarvis.ui))
                    result = r or "Done."
                    break

                elif name == "cmd_control":
                    from actions.cmd_control import cmd_control
                    r = await loop.run_in_executor(None, lambda: cmd_control(parameters=args, player=self.jarvis.ui))
                    result = r or "Done."
                    break

                elif name == "desktop_control":
                    from actions.desktop import desktop_control
                    r = await loop.run_in_executor(None, lambda: desktop_control(parameters=args, player=self.jarvis.ui))
                    result = r or "Done."
                    break

                elif name == "code_helper":
                    from actions.code_helper import code_helper
                    r = await loop.run_in_executor(None, lambda: code_helper(parameters=args, player=self.jarvis.ui, speak=self.jarvis.speak))
                    result = r or "Done."
                    break

                elif name == "dev_agent":
                    from actions.dev_agent import dev_agent
                    r = await loop.run_in_executor(None, lambda: dev_agent(parameters=args, player=self.jarvis.ui, speak=self.jarvis.speak))
                    result = r or "Done."
                    break

                elif name == "agent_task":
                    from agent.task_queue import get_queue, TaskPriority
                    priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
                    priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
                    task_id  = get_queue().submit(goal=args.get("goal", ""), priority=priority, speak=self.jarvis.speak)
                    result   = f"Task started (ID: {task_id})."
                    break

                elif name == "website_builder":
                    from actions.website_builder import build_website
                    from actions.website_builder.plugins import get_template, list_templates

                    prompt      = args.get("prompt", "")
                    deploy_to   = args.get("deploy_to", "none")
                    tmpl_name   = args.get("use_template", "")

                    _wbw = None
                    if _WIDGETS_OK:
                        from ui.build_widget import BuildWidget
                        _wbw = BuildWidget.launch(self.jarvis.ui.root, "WEBSITE", prompt or tmpl_name or "New Site")

                    # Template shortcut
                    if tmpl_name:
                        from actions.website_builder.plugins import get_template
                        tmpl = get_template(tmpl_name)
                        if tmpl:
                            plan_overrides = {"site_name": prompt or tmpl.plan_data.get("site_name", "My Site")}
                            from actions.website_builder.engine import WebsiteEngine
                            from actions.website_builder.brain import WebsiteBrain
                            engine = WebsiteEngine(
                                log_callback=lambda m: self.jarvis.ui.write_log(f"[web] {m}"),
                                widget=_wbw
                            )
                            plan   = tmpl.to_plan(overrides=plan_overrides)
                            proj_dir = engine.scaffold(plan)
                            engine.install(proj_dir)
                            url = engine.start_dev_server(proj_dir, plan)
                            result = f"Template '{tmpl_name}' banaya!\nURL: {url}\nFolder: {proj_dir}"
                        else:
                            result = f"Template '{tmpl_name}' nahi mili.\n\n{list_templates()}"
                    else:
                        result = await loop.run_in_executor(
                            None,
                            lambda: build_website(
                                prompt,
                                player=self.jarvis.ui,
                                deploy_to=deploy_to,
                                _widget_ref=_wbw
                            )
                        )

                    if _wbw:
                        self.jarvis.ui.root.after(0, lambda: _wbw.show_done())

                    # Handle clarification needed
                    if result and "[NEEDS_CLARIFICATION]" in result:
                        result = result.replace("[NEEDS_CLARIFICATION]", "").strip()

                    break

                elif name == "app_builder":
                    from actions.app_builder import build_mobile_app
                    from actions.app_builder.builder import (
                        get_app_template, list_app_templates, FlutterEngine)

                    prompt    = args.get("prompt", "")
                    tmpl_name = args.get("use_template", "")
                    do_apk    = args.get("build_apk", False)

                    _abw = None
                    if _WIDGETS_OK:
                        from ui.build_widget import BuildWidget
                        _abw = BuildWidget.launch(self.jarvis.ui.root, "MOBILE APP", prompt or tmpl_name or "New App")

                    if tmpl_name:
                        tmpl = get_app_template(tmpl_name)
                        if tmpl:
                            def _build_from_tmpl():
                                engine = FlutterEngine(
                                    log_callback=lambda m: self.jarvis.ui.write_log(f"[app] {m}"),
                                    widget=_abw
                                )
                                plan = tmpl.to_plan({"app_name": prompt or tmpl.plan_data["app_name"]})
                                proj = engine.create_project(plan)
                                engine.scaffold(proj, plan)
                                engine.pub_get(proj)
                                return engine.run_on_device(proj, plan)
                            result = await loop.run_in_executor(None, _build_from_tmpl)
                            result = f"Template '{tmpl_name}' built!\n{result}"
                        else:
                            result = f"Template '{tmpl_name}' nahi mili.\n\n{list_app_templates()}"
                    else:
                        result = await loop.run_in_executor(
                            None,
                            lambda: build_mobile_app(
                                prompt,
                                player=self.jarvis.ui,
                                build_apk=do_apk,
                                _widget_ref=_abw
                            )
                        )

                    if _abw:
                        self.jarvis.ui.root.after(0, lambda: _abw.show_done())

                    if result and "[NEEDS_CLARIFICATION]" in result:
                        result = result.replace("[NEEDS_CLARIFICATION]", "").strip()

                    break

                elif name == "web_search":
                    from actions.web_search import web_search as web_search_action
                    query = args.get("query", "")
                    _wsw = None
                    if _WIDGETS_OK and query:
                        try:
                            _wsw = WebSearchWidget.launch(self.jarvis.ui.root, query)
                        except Exception as _e:
                            print(f"[Widget] {_e}")
                    if query:
                        self.jarvis.ui.root.after(0, lambda q=query: self.jarvis.ui.open_browser_panel(q))
                    r = await loop.run_in_executor(
                        None, lambda: web_search_action(parameters=args, player=self.jarvis.ui))
                    result = r or "Done."
                    if _wsw:
                        self.jarvis.ui.root.after(0, lambda r=result: _wsw.show_result(r))
                    break

                elif name == "computer_control":
                    from actions.computer_control import computer_control
                    r = await loop.run_in_executor(None, lambda: computer_control(parameters=args, player=self.jarvis.ui))
                    result = r or "Done."
                    break

                elif name == "game_updater":
                    from actions.game_updater import game_updater
                    r = await loop.run_in_executor(None, lambda: game_updater(parameters=args, player=self.jarvis.ui, speak=self.jarvis.speak))
                    result = r or "Done."
                    break

                elif name == "flight_finder":
                    from actions.flight_finder import flight_finder
                    r = await loop.run_in_executor(None, lambda: flight_finder(parameters=args, player=self.jarvis.ui))
                    result = r or "Done."
                    break

                elif name == "news_report":
                    from actions.news import news_report
                    r = await loop.run_in_executor(None, lambda: news_report(parameters=args, player=self.jarvis.ui))
                    result = r or "Done."
                    break

                elif name == "daily_briefing":
                    from actions.daily_briefing import get_daily_briefing
                    r = await loop.run_in_executor(None, lambda: get_daily_briefing(parameters=args, player=self.jarvis.ui))
                    result = r or "Done."
                    break

                elif name == "workflow_chain":
                    from actions.workflow_chains import workflow_chains
                    r = await loop.run_in_executor(None, lambda: workflow_chains(parameters=args, player=self.jarvis.ui))
                    result = r or "Done."
                    break

                else:
                    result = f"Unknown tool: {name}"
                    break

            except Exception as e:
                attempts += 1
                if attempts < max_attempts:
                    print(f"[Self-Healing] [WARN] Attempt {attempts} failed for {name}: {e}. Retrying...")
                    if name == "file_manager" and "path" in args:
                        clean_path = args["path"].strip().strip("'\"").replace("\\\\", "\\")
                        args["path"] = clean_path
                    await asyncio.sleep(0.2)
                    continue
                
                suggestion = self.FALLBACK_SUGGESTIONS.get(name, "Sir, something went wrong. Try another approach?")
                error_str = str(e)
                if isinstance(e, FileNotFoundError) or "No such file" in error_str:
                    err_msg = f"File or directory not found: {args.get('path', '')}"
                elif isinstance(e, PermissionError) or "Access is denied" in error_str:
                    err_msg = f"Permission denied for path: {args.get('path', '')}"
                elif isinstance(e, OSError) and ("Invalid argument" in error_str or "syntax" in error_str.lower()):
                    err_msg = f"Invalid file path syntax: {args.get('path', '')}"
                else:
                    err_msg = error_str
                    
                result = f"Error: {err_msg}\n[SUGGESTION]: {suggestion}"
                traceback.print_exc()
                self.jarvis.speak_error(name, e)
                break
        return result
