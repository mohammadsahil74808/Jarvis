Set WshShell = CreateObject("WScript.Shell")
' Get the directory of this script
strPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
' Command to run python in windowless mode (pythonw.exe)
' Change "pythonw.exe" to your full python path if it's not in PATH
WshShell.Run "pythonw.exe """ & strPath & "\clap_launcher.py""", 0, False
Set WshShell = Nothing
