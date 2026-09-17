# Stop the Validation Web Console and any local Python Validation processes using its ports.
$ErrorActionPreference = 'SilentlyContinue'

$ports = @(8088, 8080, 8081, 8082)
foreach ($port in $ports) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
}

Write-Host 'Validation local services stopped.'
