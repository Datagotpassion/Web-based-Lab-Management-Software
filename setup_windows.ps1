<#
.SYNOPSIS
    Set up the Lab Management System on a Windows PC.

.DESCRIPTION
    Does everything between cloning this repository and having a working
    installation: a virtual environment, dependencies, a database, Desktop and
    Start Menu shortcuts, and the scheduled tasks for hourly backups and for
    syncing to a freezer-side display.

    Safe to run again. Each step reports whether it did anything, so re-running
    after a change is a normal way to use it rather than a risk.

.PARAMETER WithExamples
    Create a demonstration database with invented contents instead of an empty
    one, to look around before entering real data.

.PARAMETER DisplayHost
    Hostname or address of a Raspberry Pi display to sync to. Omit if you are
    not using one; the sync task is then skipped.

.PARAMETER DisplayUser
    Account on that Pi. Defaults to 'pi'.

.EXAMPLE
    .\setup_windows.ps1 -WithExamples

.EXAMPLE
    .\setup_windows.ps1 -DisplayHost labfridge.local -DisplayUser labuser
#>

[CmdletBinding()]
param(
    [switch]$WithExamples,
    [string]$DisplayHost,
    [string]$DisplayUser = 'pi'
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }
function Ok($text)   { Write-Host "    $text" -ForegroundColor Green }
function Note($text) { Write-Host "    $text" -ForegroundColor DarkGray }
function Warn($text) { Write-Host "    ! $text" -ForegroundColor Yellow }

# --------------------------------------------------------------- Python
Step 'Python'
$python = $null
foreach ($candidate in @('python', 'python3', 'py')) {
    try {
        $version = & $candidate --version 2>&1
        if ($version -match 'Python (\d+)\.(\d+)') {
            if ([int]$Matches[1] -ge 3 -and [int]$Matches[2] -ge 9) {
                $python = $candidate
                Ok "$version"
                break
            }
        }
    } catch { }
}
if (-not $python) {
    Warn 'Python 3.9 or newer was not found.'
    Warn 'Install it from https://www.python.org/downloads/ and tick'
    Warn '"Add Python to PATH", then run this again.'
    exit 1
}

# ------------------------------------------------------- virtual environment
Step 'Virtual environment'
if (Test-Path "$root\venv\Scripts\python.exe") {
    Ok 'already present'
} else {
    & $python -m venv venv
    Ok 'created'
}
$venvPy  = "$root\venv\Scripts\python.exe"
$venvPyw = "$root\venv\Scripts\pythonw.exe"

Step 'Dependencies'
& $venvPy -m pip install --quiet --upgrade pip
& $venvPy -m pip install --quiet -r requirements.txt
$installed = & $venvPy -m pip list --format=freeze |
             Select-String -Pattern 'flask|waitress|werkzeug'
$installed | ForEach-Object { Note $_ }

# ------------------------------------------------------------------ database
Step 'Database'
if (Test-Path "$root\lab_management.db") {
    Ok 'existing database kept'
} elseif ($WithExamples) {
    & $venvPy examples\seed_example_data.py --db lab_management.db | Out-Null
    Ok 'created with example contents'
    Note 'Invented data, to look around. Delete the file to start clean.'
} else {
    # Starting the app once creates the schema.
    & $venvPy -c "import app" 2>&1 | Out-Null
    Ok 'created empty'
    Note 'Run with -WithExamples instead if you would rather see a worked example.'
}

# ----------------------------------------------------------------- shortcuts
Step 'Shortcuts'
$shell = New-Object -ComObject WScript.Shell
$icon  = "$root\static\labmanagement.ico"
foreach ($dir in @([Environment]::GetFolderPath('Desktop'),
                   [Environment]::GetFolderPath('Programs'))) {
    $lnk = Join-Path $dir 'Lab Management.lnk'
    $sc = $shell.CreateShortcut($lnk)
    $sc.TargetPath       = $venvPyw
    $sc.Arguments        = "`"$root\launch_app.pyw`""
    $sc.WorkingDirectory = $root
    if (Test-Path $icon) { $sc.IconLocation = "$icon,0" }
    $sc.Description      = 'Lab Management System'
    $sc.Save()
    Ok (Split-Path $dir -Leaf)
}

# ------------------------------------------------------------ scheduled jobs
function Register-LabTask($name, $arguments, $trigger, $description) {
    try { Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction Stop } catch { }
    $action = New-ScheduledTaskAction -Execute $venvPyw -Argument $arguments `
                                      -WorkingDirectory $root
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
        -Settings $settings -Description $description | Out-Null
}

Step 'Hourly backup'
$hourly = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(1) `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
Register-LabTask 'LabManagement Backup' 'backup_db.py --quiet' $hourly `
    'Hourly copy of the lab database to the project folder, a sibling folder, and a cloud-synced folder.'
& $venvPy backup_db.py --quiet
Ok 'registered and run once'
& $venvPy -c "from backup_db import default_destinations; [print('    ->', d) for d in default_destinations()]"

# -------------------------------------------------------------- the display
if ($DisplayHost) {
    Step "Freezer display ($DisplayHost)"

    $keyPath = "$env:USERPROFILE\.ssh\id_ed25519_labpi"
    if (-not (Test-Path $keyPath)) {
        New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null
        & ssh-keygen -t ed25519 -f $keyPath -N '""' -C 'labmanagement-display' | Out-Null
        Ok 'created an SSH key for the display'
    } else {
        Ok 'SSH key already present'
    }

    # Site settings live outside the code so nothing specific is committed.
    $state = @{ host = $DisplayHost; user = $DisplayUser
                remote_dir = "/home/$DisplayUser/LabManagement" }
    $statePath = "$root\.sync_state.json"
    if (Test-Path $statePath) {
        $existing = Get-Content $statePath -Raw | ConvertFrom-Json
        $existing.PSObject.Properties | ForEach-Object {
            if (-not $state.ContainsKey($_.Name)) { $state[$_.Name] = $_.Value }
        }
    }
    $state | ConvertTo-Json | Set-Content $statePath -Encoding utf8
    Ok 'saved display settings to .sync_state.json'

    $every5 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Minutes 5) `
        -RepetitionDuration (New-TimeSpan -Days 3650)
    Register-LabTask 'LabManagement Sync to Pi' 'sync_to_pi.py --quiet' $every5 `
        'Pushes the lab database to the freezer display every 5 minutes. One way; the display never writes.'
    Ok 'sync task registered'

    $target = $DisplayUser + '@' + $DisplayHost
    Write-Host ''
    Note 'Next, on the display itself:'
    Note '  1. Copy the key across (it will ask for the Pi password once):'
    Note ('       type $env:USERPROFILE\.ssh\id_ed25519_labpi.pub | ssh ' +
          $target + ' "cat >> ~/.ssh/authorized_keys"')
    Note '  2. Clone this repository there and run the Pi setup:'
    Note '       git clone REPO-URL ~/LabManagement'
    Note '       cd ~/LabManagement; bash deploy/setup-pi.sh'
    Note '  See deploy/README.md for the touchscreen itself.'
} else {
    Step 'Freezer display'
    Note 'Skipped. Re-run with -DisplayHost <name> to set one up.'
}

# ----------------------------------------------------------------- finished
Step 'Done'
Ok 'Open "Lab Management" from your Desktop or Start Menu.'
Note 'Tests:   .\venv\Scripts\python.exe -m pytest tests -q'
Note 'Backups: .\venv\Scripts\python.exe backup_db.py'
Write-Host ''
