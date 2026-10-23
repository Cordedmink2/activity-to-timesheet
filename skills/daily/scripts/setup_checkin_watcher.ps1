<#
.SYNOPSIS
  Sets up the check-in watcher: installs aw-watcher-ask-away at a pinned version for the
  current user and registers ONE per-user scheduled task that starts it at logon.

.DESCRIPTION
  The watcher asks you, when you come back from being away, what you were doing, and
  writes the answer to ActivityWatch. The billables daily skill reads it and puts it to you
  as a question; nothing is billed without your yes (ADR-0009).

  No admin rights. The task runs as the current user, logon type Interactive (the dialog
  needs your desktop), run level Limited, and restarts if the watcher stops. Nothing else
  is installed machine-wide.

  Re-running is safe: -Force replaces a task of the same name.

  Needs Python 3.11 or newer (the pinned watcher requires it).

.EXAMPLE
  powershell -File setup_checkin_watcher.ps1 -DryRun
  # prints the task it would register and exits; installs nothing, registers nothing

.EXAMPLE
  powershell -File setup_checkin_watcher.ps1 -PythonExe C:\Python313\python.exe -Force

  Check:   Get-ScheduledTask -TaskName CheckinWatcher
  Remove:  Unregister-ScheduledTask -TaskName CheckinWatcher -Confirm:$false
           python -m pip uninstall aw-watcher-ask-away
#>
[CmdletBinding()]
param(
    [string]$TaskName  = "CheckinWatcher",
    [string]$PythonExe = "",
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Package = "aw-watcher-ask-away"
$Spec    = "aw-watcher-ask-away==0.0.6"

function Test-UsablePython([string]$exe) {
    # Probed by running it: the Windows Store alias exists and runs nothing. The pinned
    # watcher needs 3.11+.
    if (-not $exe) { return $false }
    try {
        & { $ErrorActionPreference = 'Continue'
            & $exe -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null }
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

$candidates = @()
if ($PythonExe) { $candidates += $PythonExe }
else {
    foreach ($name in @("python", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { $candidates += $cmd.Source }
    }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        $resolved = & { $ErrorActionPreference = 'Continue'; & $py.Source -3 -c "import sys; print(sys.executable)" 2>$null }
        if ($resolved) { $candidates += "$resolved".Trim() }
    }
}
$found = $null
foreach ($c in $candidates) { if (Test-UsablePython $c) { $found = $c; break } }
if (-not $found) {
    throw ("No usable Python 3.11+ found. Probed: " + ($candidates -join ", ") +
           ". Install Python 3.11 or newer, or pass -PythonExe <path\to\python.exe>.")
}

$dir    = Split-Path $found
$base   = [System.IO.Path]::GetFileNameWithoutExtension($found) -replace 'w$', ''
$winExe = Join-Path $dir ($base + "w.exe")
$runExe = if ((Test-Path $winExe) -and (Get-Item $winExe).Length -gt 0) { $winExe } else { $found }

Write-Host "Python (run)   : $runExe"
Write-Host "Package        : $Spec"

$trigger   = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$action    = New-ScheduledTaskAction -Execute $runExe -Argument "-m aw_watcher_ask_away"
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -StartWhenAvailable `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0)

if ($DryRun) {
    Write-Host ""
    Write-Host "DRYRUN Task name   : $TaskName"
    Write-Host "DRYRUN Package     : $Spec"
    Write-Host "DRYRUN Execute     : $($action.Execute)"
    Write-Host "DRYRUN Arguments   : $($action.Arguments)"
    Write-Host "DRYRUN Trigger     : AtLogOn ($($trigger.CimClass.CimClassName))"
    Write-Host "DRYRUN LogonType   : $($principal.LogonType)"
    Write-Host "DRYRUN RunLevel    : $($principal.RunLevel)"
    Write-Host "DRYRUN Restart     : $($settings.RestartCount) times, every $($settings.RestartInterval)"
    Write-Host ""
    Write-Host "Dry run: nothing installed, no task registered."
    exit 0
}

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing -and -not $Force) {
    throw "A task named '$TaskName' already exists. Re-run with -Force to replace it."
}

Write-Host "Installing $Spec (user scope)..."
& { $ErrorActionPreference = 'Continue'; & $found -m pip install --user --quiet $Spec }
if ($LASTEXITCODE -ne 0) { throw "pip could not install $Spec." }

Register-ScheduledTask -TaskName $TaskName -Trigger $trigger -Action $action `
    -Principal $principal -Settings $settings `
    -Description "Check-in watcher for the billables daily skill." -Force | Out-Null

Write-Host ""
Write-Host "Registered '$TaskName': starts at logon, restarts on failure, no admin."
Write-Host "Check status any time with:  Get-ScheduledTask -TaskName $TaskName"
Write-Host "Remove with:  Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
