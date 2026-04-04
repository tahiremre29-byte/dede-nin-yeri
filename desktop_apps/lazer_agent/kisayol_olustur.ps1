$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut("$env:USERPROFILE\Desktop\DD1 Agent.lnk")
$s.TargetPath = "cmd.exe"
$s.Arguments = "/c cd /d C:\Users\DDSOUND\Desktop\exemiz\dd1_lazer_agent && python main_app.py"
$s.WorkingDirectory = "C:\Users\DDSOUND\Desktop\exemiz\dd1_lazer_agent"
$s.WindowStyle = 7
$s.Save()
Write-Host "Kisayol olusturuldu: $env:USERPROFILE\Desktop\DD1 Agent.lnk"
