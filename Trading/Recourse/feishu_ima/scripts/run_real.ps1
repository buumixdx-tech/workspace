[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
Set-Location 'D:\WorkSpace\Trading\Recourse\feishu_ima'
$env:FEISHU_PREPROCESS_DB = 'D:\WorkSpace\Trading\Recourse\feishu_ext\data\preprocess.db'
Write-Host "FEISHU_PREPROCESS_DB=$env:FEISHU_PREPROCESS_DB"
Write-Host "START"
python -u feishu_to_ima.py --real 2>&1 | Tee-Object -FilePath 'D:\WorkSpace\Trading\Recourse\logs\feishu_to_ima_manual.log' -Append
Write-Host "EXIT=$LASTEXITCODE"
