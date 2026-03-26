$batPath = "C:\Users\Innovapath\Desktop\job_engine\project-job-application-engine\run_engine.bat"
$workDir = "C:\Users\Innovapath\Desktop\job_engine\project-job-application-engine"

$action   = New-ScheduledTaskAction -Execute $batPath -WorkingDirectory $workDir
$trigger  = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "09:00AM"
$settings = New-ScheduledTaskSettingsSet `
                -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
                -RestartCount 1 `
                -RestartInterval (New-TimeSpan -Minutes 30) `
                -StartWhenAvailable

Register-ScheduledTask `
    -TaskName    "JobApplicationEngine_Weekly" `
    -Action      $action `
    -Trigger     $trigger `
    -Settings    $settings `
    -Description "Runs the Job Application Engine every Monday at 9:00 AM" `
    -Force

Write-Host "Task registered successfully. Verifying..." -ForegroundColor Green
schtasks /Query /TN "JobApplicationEngine_Weekly" /FO LIST
