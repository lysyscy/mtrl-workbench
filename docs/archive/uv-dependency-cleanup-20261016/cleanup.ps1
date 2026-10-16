$ErrorActionPreference = 'Stop'
$taskRoot = 'D:\dev\mtrl-workbench\.scratch'
$targets = @(
    'D:\dev\mtrl-workbench\.scratch\uv-dependency-cleanup\candidate',
    'D:\dev\mtrl-workbench\.scratch\uv-dependency-cleanup\pytest-temp',
    'D:\dev\mtrl-workbench\.scratch\local\uv-audit-cache'
)
foreach ($target in $targets) {
    if (Test-Path -LiteralPath $target) {
        $resolved = (Resolve-Path -LiteralPath $target).Path
        if ($resolved -cne $target -or -not $resolved.StartsWith($taskRoot + '\')) { throw 'Unexpected cleanup target' }
        Remove-Item -LiteralPath $resolved -Recurse
        if (Test-Path -LiteralPath $target) { throw 'Cleanup incomplete' }
        Write-Output ('Removed: ' + $target)
    }
}
