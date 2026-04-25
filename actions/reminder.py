# actions/reminder.py

import subprocess
import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Local storage path
from core.config import BASE_DIR
REMINDERS_FILE = BASE_DIR / "memory" / "reminders.json"

def _load_reminders():
    if REMINDERS_FILE.exists():
        try:
            with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def _save_reminders(reminders):
    REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, indent=2)

def reminder(
    parameters: dict,
    response: str | None = None,
    player=None,
    session_memory=None
) -> str:
    """
    Manages reminders (set, list, delete).
    """

    action = parameters.get("action", "set")
    
    if action == "list":
        reminders = _load_reminders()
        # Clean expired ones
        now = datetime.now()
        reminders = [r for r in reminders if datetime.strptime(r['datetime'], "%Y-%m-%d %H:%M") > now]
        _save_reminders(reminders)
        
        if not reminders:
            return "Sir, you have no pending reminders right now."
        
        output = "Sir, here are your pending reminders:\n"
        for i, r in enumerate(reminders, 1):
            dt = datetime.strptime(r['datetime'], "%Y-%m-%d %H:%M").strftime("%B %d at %I:%M %p")
            output += f"{i}. {r['message']} on {dt}\n"
        return output

    if action == "delete":
        message_to_find = parameters.get("message", "").lower()
        if not message_to_find:
            return "Please specify the reminder message to delete, sir."
        
        reminders = _load_reminders()
        new_reminders = [r for r in reminders if message_to_find not in r['message'].lower()]
        
        if len(new_reminders) == len(reminders):
            return f"I couldn't find any reminder with '{message_to_find}', sir."
        
        # Also try to delete from schtasks
        for r in reminders:
            if message_to_find in r['message'].lower():
                task_name = r.get("task_name")
                if task_name:
                    subprocess.run(f'schtasks /Delete /TN "{task_name}" /F', shell=True, capture_output=True)
        
        _save_reminders(new_reminders)
        return f"Successfully deleted reminders matching '{message_to_find}', sir."

    # Default action: SET
    date_str = parameters.get("date")
    time_str = parameters.get("time")
    message  = parameters.get("message", "Reminder")

    if not date_str or not time_str:
        return "I need both a date and a time to set a reminder."

    try:
        target_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

        if target_dt <= datetime.now():
            return "That time is already in the past."

        task_name    = f"MARKReminder_{target_dt.strftime('%Y%m%d_%H%M')}"
        safe_message = message.replace('"', '').replace("'", "").strip()[:200]

        python_exe = sys.executable
        if python_exe.lower().endswith("python.exe"):
            pythonw = python_exe.replace("python.exe", "pythonw.exe")
            if os.path.exists(pythonw):
                python_exe = pythonw

        temp_dir      = os.environ.get("TEMP", "C:\\Temp")
        notify_script = os.path.join(temp_dir, f"{task_name}.pyw")
        project_root  = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )

        script_code = f'''import sys, os, time
sys.path.insert(0, r"{project_root}")

try:
    import winsound
    for freq in [800, 1000, 1200]:
        winsound.Beep(freq, 200)
        time.sleep(0.1)
except Exception:
    pass

try:
    from win10toast import ToastNotifier
    ToastNotifier().show_toast(
        "MARK Reminder",
        "{safe_message}",
        duration=15,
        threaded=False
    )
except Exception:
    try:
        import subprocess
        subprocess.run(["msg", "*", "/TIME:30", "{safe_message}"], shell=True)
    except Exception:
        pass

time.sleep(3)
try:
    os.remove(__file__)
except Exception:
    pass
'''
        with open(notify_script, "w", encoding="utf-8") as f:
            f.write(script_code)

        xml_content = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>MARK Reminder: {safe_message}</Description>
  </RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <StartBoundary>{target_dt.strftime("%Y-%m-%dT%H:%M:%S")}</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Actions>
    <Exec>
      <Command>{python_exe}</Command>
      <Arguments>"{notify_script}"</Arguments>
    </Exec>
  </Actions>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <WakeToRun>true</WakeToRun>
    <ExecutionTimeLimit>PT5M</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Principals>
    <Principal>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
</Task>'''

        xml_path = os.path.join(temp_dir, f"{task_name}.xml")
        with open(xml_path, "w", encoding="utf-16") as f:
            f.write(xml_content)

        result = subprocess.run(
            f'schtasks /Create /TN "{task_name}" /XML "{xml_path}" /F',
            shell=True, capture_output=True, text=True
        )

        try:
            os.remove(xml_path)
        except Exception:
            pass

        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip()
            print(f"[Reminder] ❌ schtasks failed: {err}")
            try:
                os.remove(notify_script)
            except Exception:
                pass
            return "I couldn't schedule the reminder due to a system error."

        # Save to local JSON
        reminders = _load_reminders()
        reminders.append({
            "datetime": target_dt.strftime("%Y-%m-%d %H:%M"),
            "message": message,
            "task_name": task_name
        })
        _save_reminders(reminders)

        if player:
            player.write_log(f"[reminder] set for {date_str} {time_str}")

        return f"Reminder set for {target_dt.strftime('%B %d at %I:%M %p')}."

    except ValueError:
        return "I couldn't understand that date or time format."

    except Exception as e:
        return f"Something went wrong while scheduling the reminder: {str(e)[:80]}"

    except ValueError:
        return "I couldn't understand that date or time format."

    except Exception as e:
        return f"Something went wrong while scheduling the reminder: {str(e)[:80]}"
