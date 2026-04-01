param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8787,
    [switch]$SkipPlaywrightInstall,
    [switch]$SetupOnly
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[SiriusToolbox] $Message" -ForegroundColor Cyan
}

function Test-PythonVersion {
    param([string]$ExecutablePath)

    if (-not (Test-Path -Path $ExecutablePath)) {
        return $false
    }

    $version = & $ExecutablePath -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($LASTEXITCODE -ne 0) {
        return $false
    }

    return $version -eq "3.12" -or $version.StartsWith("3.12")
}

function Resolve-PythonExecutable {
    $knownPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles(x86)\Python312\python.exe"
    )

    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            & py -3.12 -c "import sys; print(sys.version)" | Out-Null
            if ($LASTEXITCODE -eq 0) {
                return "py -3.12"
            }
        }
        catch {
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        $pythonCmd = (Get-Command python).Source
        if (Test-PythonVersion -ExecutablePath $pythonCmd) {
            return $pythonCmd
        }
    }

    foreach ($path in $knownPaths) {
        if (Test-PythonVersion -ExecutablePath $path) {
            return $path
        }
    }

    return $null
}

function Install-Python312 {
    Write-Step "Python 3.12 not found. Installing with winget..."

    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget is not available. Install Python 3.12 manually, then rerun this script."
    }

    & winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install Python 3.12 via winget."
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

Write-Step "Workspace: $repoRoot"

$pythonRef = Resolve-PythonExecutable
if (-not $pythonRef) {
    Install-Python312
    $pythonRef = Resolve-PythonExecutable
}

if (-not $pythonRef) {
    throw "Python 3.12 still not detected. Open a new terminal and rerun this script."
}

Write-Step "Using Python: $pythonRef"

if ($pythonRef -eq "py -3.12") {
    & py -3.12 -m venv .venv
}
else {
    & $pythonRef -m venv .venv
}

if ($LASTEXITCODE -ne 0) {
    throw "Failed to create virtual environment."
}

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -Path $venvPython)) {
    throw "Virtual environment python not found at $venvPython"
}

Write-Step "Upgrading pip..."
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip."
}

Write-Step "Installing project dependencies..."
& $venvPython -m pip install -e .
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install project dependencies."
}

if (-not $SkipPlaywrightInstall) {
    Write-Step "Installing Playwright Chromium runtime..."
    & $venvPython -m playwright install chromium
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install Playwright Chromium."
    }
}
else {
    Write-Step "Skipped Playwright Chromium installation."
}

if ($SetupOnly) {
    Write-Step "Environment setup complete."
    exit 0
}

Write-Step "Starting WebUI at http://${BindHost}:$Port"
& $venvPython main.py webui --host $BindHost --port $Port
