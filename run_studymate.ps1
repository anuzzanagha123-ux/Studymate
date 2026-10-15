$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$mysqlServer = 'C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe'
$mysqlBase = 'C:\Program Files\MySQL\MySQL Server 8.4'
$mysqlData = Join-Path $PSScriptRoot 'mysql-data'
$mysqlPidFile = Join-Path $mysqlData 'studymate-mysqld.pid'
$mysqlErrorLog = Join-Path $mysqlData 'studymate-mysqld.err'

function Test-LocalPort {
    param([int]$Port)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne(1000)) {
            return $false
        }
        $client.EndConnect($connect)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

if (-not (Test-LocalPort -Port 3307)) {
    if (-not (Test-Path $mysqlServer) -or -not (Test-Path (Join-Path $mysqlData 'ibdata1'))) {
        throw 'The project MySQL server or its data directory is missing.'
    }

    $mysqlArgs = @(
        '--no-defaults'
        ('"--basedir={0}"' -f $mysqlBase)
        "--datadir=$mysqlData"
        '--port=3307'
        '--bind-address=127.0.0.1'
        '--mysqlx=OFF'
        "--pid-file=$mysqlPidFile"
        "--log-error=$mysqlErrorLog"
    )
    Start-Process -FilePath $mysqlServer -ArgumentList $mysqlArgs -WindowStyle Hidden

    $mysqlReady = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if (Test-LocalPort -Port 3307) {
            $mysqlReady = $true
            break
        }
        Start-Sleep -Seconds 1
    }
    if (-not $mysqlReady) {
        throw "The project MySQL database did not start. Check $mysqlErrorLog."
    }
}

$password = [Environment]::GetEnvironmentVariable('DJANGO_DB_PASSWORD', 'User')
if (-not $password) {
    $securePassword = Read-Host 'Enter the MySQL password for studymate_user' -AsSecureString
    $password = [System.Net.NetworkCredential]::new('', $securePassword).Password
    [Environment]::SetEnvironmentVariable('DJANGO_DB_PASSWORD', $password, 'User')
}

$env:DJANGO_DB_ENGINE = 'mysql'
$env:DJANGO_DB_NAME = 'studymate'
$env:DJANGO_DB_USER = 'studymate_user'
$env:DJANGO_DB_HOST = '127.0.0.1'
$env:DJANGO_DB_PORT = '3307'
$env:DJANGO_DB_PASSWORD = $password

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw 'The project virtual environment is missing at .venv\Scripts\python.exe.'
}

& $python manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) {
    throw 'Django migrations failed; runserver was not started.'
}

Write-Host 'Starting StudyMate with the existing MySQL database on port 3307...'
Write-Host ''
Write-Host 'StudyMate is available at: http://127.0.0.1:8000/' -ForegroundColor Cyan
Write-Host 'Register: http://127.0.0.1:8000/register/'
Write-Host 'Login:    http://127.0.0.1:8000/login/'
Write-Host ''
& $python manage.py runserver 127.0.0.1:8000
exit $LASTEXITCODE
