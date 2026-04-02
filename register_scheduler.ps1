$batPath = "C:\Users\remot\Desktop\automation_engine\project-job-application-engine\run_engine.bat"
$workDir = "C:\Users\remot\Desktop\automation_engine\project-job-application-engine"

$action   = New-ScheduledTaskAction -Execute $batPath -WorkingDirectory $workDir
$trigger  = New-ScheduledTaskTrigger -Daily -At "09:32AM"
$settings = New-ScheduledTaskSettingsSet `
                -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
                -StartWhenAvailable

Register-ScheduledTask `
    -TaskName    "JobApplicationEngine_Daily" `
    -Action      $action `
    -Trigger     $trigger `
    -Settings    $settings `
    -Description "Runs the Job Application Engine every day at 09:32 AM" `
    -Force

Write-Host "Task registered successfully. Verifying..." -ForegroundColor Green
schtasks /Query /TN "JobApplicationEngine_Daily" /FO LIST
