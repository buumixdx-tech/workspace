[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
Set-Location 'D:\WorkSpace\Trading\Recourse\feishu_ima'
Write-Host "START dry run (no FEISHU_PREPROCESS_DB env, use new default)"
python -u feishu_to_ima.py 2>&1 | Tee-Object -FilePath 'D:\WorkSpace\Trading\Recourse\logs\feishu_to_ima_dry.log' -Append
Write-Host "EXIT=$LASTEXITCODE"
