<#!
.SYNOPSIS
  Helper to (optionally) run a short crawl, dump status snapshot, and open dashboard.
.DESCRIPTION
  Parameters:
    -Pages <int>        Approx max pages for optional crawl (default 50)
    -Concurrency <int>  Worker concurrency (default 10)
    -RunCrawl           If supplied, performs a crawl before dumping status.
    -SkipOpen           If supplied, does not auto-open dashboard.html.
.EXAMPLES
  ./scripts/view_status.ps1 -RunCrawl -Pages 100 -Concurrency 30
  ./scripts/view_status.ps1          # just dumps status & opens dashboard
  ./scripts/view_status.ps1 -SkipOpen # dump only
#>
param(
    [int]$Pages = 50,
    [int]$Concurrency = 10,
    [switch]$RunCrawl,
    [switch]$SkipOpen
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-Python {
    $root = (Resolve-Path "$PSScriptRoot/.." ).Path
    $venvPy = Join-Path $root '.venv/Scripts/python.exe'
    if (Test-Path $venvPy) { return $venvPy }
    return 'python'
}

function Invoke-PyMain {
    param([string[]]$Args)
    $py = Get-Python
    Write-Host "[py] $py -m crawler.main $($Args -join ' ')" -ForegroundColor Cyan
    & $py -m crawler.main @Args
}

$root = (Resolve-Path "$PSScriptRoot/.." ).Path
Push-Location $root
try {
    if ($RunCrawl) {
        Write-Host "[step] Running crawl (target pages: $Pages, concurrency: $Concurrency)" -ForegroundColor Yellow
        Invoke-PyMain @('run', '--concurrency', $Concurrency.ToString(), '--max-pages', $Pages.ToString())
    }
    else {
        Write-Host "[skip] Crawl not requested" -ForegroundColor DarkYellow
    }

    Write-Host "[step] Dumping status snapshot" -ForegroundColor Yellow
    Invoke-PyMain @('dump-status')

    $dash = Join-Path $root 'output/dashboard.html'
    if (-not (Test-Path $dash)) {
        Write-Warning "Dashboard file not found at $dash"
        return
    }

    if (-not $SkipOpen) {
        Write-Host "[open] Launching $dash" -ForegroundColor Green
        Start-Process $dash | Out-Null
    }
    else {
        Write-Host "[skip] Not opening dashboard (SkipOpen specified)" -ForegroundColor DarkYellow
    }

    $statusJson = Join-Path $root 'output/status.json'
    if (Test-Path $statusJson) {
        Write-Host "[info] status.json contents:" -ForegroundColor Magenta
        Get-Content $statusJson | Select-Object -First 30 | ForEach-Object { $_ }
    }

    $metrics = Join-Path $root 'output/metrics.json'
    if (Test-Path $metrics) {
        Write-Host "[info] metrics.json contents:" -ForegroundColor Magenta
        Get-Content $metrics | Select-Object -First 30 | ForEach-Object { $_ }
    }

    Write-Host "[done] View operation complete." -ForegroundColor Green
}
finally {
    Pop-Location
}
