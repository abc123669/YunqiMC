# Stops only the YunqiMC test bot. The benchmark runner then saves and stops
# its own isolated server and records the run as incomplete.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root 'bench\longrun.pid'
if (-not (Test-Path -LiteralPath $pidFile)) { throw 'No YunqiMC benchmark supervisor PID was found.' }
$supervisorId = [int](Get-Content -LiteralPath $pidFile -Raw).Trim()
$supervisor = Get-CimInstance Win32_Process -Filter "ProcessId=$supervisorId"
if (-not $supervisor -or $supervisor.Name -ne 'python.exe' -or $supervisor.CommandLine -notlike '*bench\longrun.py*') {
    throw 'The recorded PID is not the YunqiMC benchmark supervisor.'
}
$children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$supervisorId")
$runner = @($children | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*bench\paired.py*' })
if ($runner.Count -ne 1) { throw 'The benchmark runner is not in its normal running state; retry shortly.' }
$runnerId = $runner[0].ProcessId
$bots = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$runnerId" | Where-Object {
    $_.Name -eq 'node.exe' -and $_.CommandLine -like '*bench\run.mjs*'
})
if ($bots.Count -ne 1) { throw 'The isolated test bot is not running yet; retry once the test server is ready.' }
Stop-Process -Id $bots[0].ProcessId -Force
Write-Output 'Stopped the isolated test bot. The benchmark runner will save and stop its test server and mark the run incomplete.'
