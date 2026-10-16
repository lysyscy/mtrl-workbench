$ErrorActionPreference = 'Stop'
Get-Process python* -ErrorAction SilentlyContinue | ForEach-Object {
    $taskProcess = $_
    $taskProcess.Modules | Where-Object { $_.FileName -like '*mtrl-workbench*watchfiles*' -or $_.FileName -like '*mtrl-workbench*websockets*' } | ForEach-Object {
        [PSCustomObject]@{Id=$taskProcess.Id;Process=$taskProcess.ProcessName;Module=$_.FileName}
    }
} | ConvertTo-Json
Get-CimInstance Win32_Service -Filter "Name='mtrl-workbench-server'" | Select-Object Name,State,ProcessId | ConvertTo-Json
