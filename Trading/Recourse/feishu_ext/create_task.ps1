$ErrorActionPreference = "Stop"

$taskName = "Feishu_ext_5m"
$batPath = "C:\Users\buumi\.claude\temp\run_feishu_ext_5m.bat"

# Check if task already exists
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Task exists, removing..."
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Create action
$action = New-ScheduledTaskAction -Execute $batPath

# Create trigger: once at a fixed time, with 5min repetition
$trigger = New-ScheduledTaskTrigger -Once -At "2026-07-03 16:00"
$trigger.Repetition.Interval = "PT5M"
$trigger.Repetition.Duration = "P1D"

# Create principal: SYSTEM, limited
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType "ServiceAccount" -RunLevel "Limited"

# Register task
Write-Host "Registering task..."
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Description "feishu extract pipeline (5min)" -Force

# Verify
$registered = Get-ScheduledTask -TaskName $taskName
Write-Host "Registered: $($registered.TaskName)"
Write-Host "State: $($registered.State)"
Write-Host "Trigger Interval: $($registered.Triggers[0].Repetition.Interval)"
Write-Host "Trigger Duration: $($registered.Triggers[0].Repetition.Duration)"
