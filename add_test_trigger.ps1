$taskName = "JobApplicationEngine_Weekly"
$testTime = (Get-Date).AddMinutes(2).ToString("HH:mm:ss")
$dateStr = (Get-Date).ToString("yyyy-MM-dd")

Write-Host "Setting a one-time test trigger for $dateStr at $testTime..." -ForegroundColor Cyan

# Create a one-time trigger
$newTrigger = New-ScheduledTaskTrigger -Once -At $testTime

# Add the trigger to the existing task
$task = Get-ScheduledTask -TaskName $taskName
$triggers = $task.Triggers
$triggers += $newTrigger

Set-ScheduledTask -TaskName $taskName -Trigger $triggers

Write-Host "Test trigger added successfully. Task will run in 2 minutes." -ForegroundColor Green
Write-Host "Next Run Time Info:" -ForegroundColor White
Get-ScheduledTaskInfo -TaskName $taskName | Select-Object NextRunTime
