Set WshShell = CreateObject("WScript.Shell")
' Get the folder where this VBS lives (project root)
Dim rootDir
rootDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.Run Chr(34) & rootDir & "\scripts\run.bat" & Chr(34), 0, False
