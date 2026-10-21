# Registra las tareas programadas de DATACORE en el Programador de tareas de Windows.
# Ejecútalo TÚ en una PowerShell normal cuando quieras activar la automatización:
#   powershell -ExecutionPolicy Bypass -File scripts\programar_tareas_windows.ps1
# Para quitarlas:
#   Unregister-ScheduledTask -TaskName "DATACORE*" -Confirm:$false

$raiz = Split-Path -Parent $PSScriptRoot
$python = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "No existe $python; crea el entorno virtual primero." }

$tareas = @(
    @{ Nombre = "DATACORE diario";    Args = "-m datacore.operacion diario";    Disparador = New-ScheduledTaskTrigger -Daily -At 2:00am },
    @{ Nombre = "DATACORE monitoreo"; Args = "-m datacore.operacion monitoreo"; Disparador = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 30) }
)

foreach ($t in $tareas) {
    $accion = New-ScheduledTaskAction -Execute $python -Argument $t.Args -WorkingDirectory $raiz
    $ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    Register-ScheduledTask -TaskName $t.Nombre -Action $accion -Trigger $t.Disparador -Settings $ajustes -Force | Out-Null
    Write-Host "Tarea registrada: $($t.Nombre)"
}
