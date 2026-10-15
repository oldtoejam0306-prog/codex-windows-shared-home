param([Parameter(Mandatory=$true)][string]$Settings,[switch]$CheckOnly)
$ErrorActionPreference='Stop'
$lease=$null
$ownedApp=$null
$changed=[Collections.Generic.List[string]]::new()
$previous=@{}
$settingsPath=[IO.Path]::GetFullPath($Settings)
$cfg=Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$person=@($cfg.participants | Where-Object {$_.sid -eq $sid})
if ($person.Count -ne 1 -or $person[0].profile -ne $env:USERPROFILE) {throw 'Windows identity/profile not enrolled.'}
$root=[IO.Path]::GetFullPath([string]$cfg.shared_root)
if ($root -notmatch '^[A-Za-z]:\\.+' -or $root.TrimEnd('\') -eq [IO.Path]::GetPathRoot($root).TrimEnd('\')) {throw 'Use a non-root local drive directory.'}
$home=Join-Path $root 'home'
$control=Join-Path $root 'control'
$relative=[string]$cfg.private_relative
if ([IO.Path]::IsPathRooted($relative) -or '..' -in ($relative -split '[\\/]')) {throw 'Unsafe private-relative path.'}
if ([IO.Path]::GetFullPath($env:LOCALAPPDATA) -ne (Join-Path $env:USERPROFILE 'AppData\Local')) {throw 'Redirected LOCALAPPDATA needs review.'}

function Assert-Ordinary([string]$Path) {
    $entry=Get-Item -LiteralPath $Path -Force
    if (-not $entry.PSIsContainer -or ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint)) {throw 'Missing or redirected directory.'}
}
function Assert-ExistingAncestors([string]$Path) {
    $cursor=[IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {Assert-Ordinary $cursor}
        $parent=Split-Path -Parent $cursor
        if ($parent -eq $cursor) {break}
        $cursor=$parent
    }
}
function Assert-Stopped {
    $busy=@(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -in @('ChatGPT.exe','codex.exe','codex-code-mode-host.exe','node_repl.exe','codex-computer-use.exe','codex-computer-use-swift.exe','codex-windows-sandbox.exe','codex-windows-sandbox-setup.exe')
    })
    if ($busy.Count) {throw 'Exit Codex in ALL Windows sessions. Existing processes were not stopped.'}
}
function Remove-KnownLink([string]$Path,[string]$Expected) {
    $entry=Get-Item -LiteralPath $Path -Force
    if ($entry.LinkType -ne 'Junction' -or [IO.Path]::GetFullPath([string]$entry.Target) -ne $Expected) {throw 'Unexpected link; not removed.'}
    [IO.Directory]::Delete($Path)
}
$targets=@{}
try {
    Assert-ExistingAncestors $root
    Assert-Ordinary $root
    Assert-Ordinary $home
    if (Test-Path -LiteralPath $control) {Assert-Ordinary $control}
    if (Test-Path -LiteralPath (Join-Path $home 'auth.json')) {throw 'Shared auth.json exists; it was not opened or removed.'}
    if (-not (Test-Path -LiteralPath (Join-Path $home 'SHARED-HOME-READY.json'))) {throw 'Prepare and review the migration before creating SHARED-HOME-READY.json.'}
    Assert-Stopped
    if ($cfg.allow_private_state_binding -ne $true) {throw 'Private authentication/browser binding has not been enabled.'}
    $app=[string]$cfg.app_executable
    if (-not $app) {
        $package=Get-AppxPackage -Name 'OpenAI.Codex' | Sort-Object Version -Descending | Select-Object -First 1
        if ($null -eq $package) {throw 'Codex MSIX package is not registered for this user.'}
        if ($cfg.expected_package_version -and [string]$package.Version -ne $cfg.expected_package_version) {throw 'Unexpected app version.'}
        $app=Join-Path $package.InstallLocation 'app\ChatGPT.exe'
    }
    if (-not (Test-Path -LiteralPath $app -PathType Leaf)) {throw 'App executable missing.'}
    $python=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {throw 'Bundled Python 3.11+ runtime is required.'}
    $privateBase=Join-Path $env:LOCALAPPDATA $relative
    Assert-ExistingAncestors $privateBase
    foreach ($name in @('secrets','browser','computer-use','node_repl')) {
        $link=Join-Path $home $name
        $targets[$name]=Join-Path $privateBase $name
        $previous[$name]=$null
        $entry=Get-Item -LiteralPath $link -Force -ErrorAction SilentlyContinue
        if ($null -ne $entry) {
            $known=@($cfg.participants | ForEach-Object {Join-Path $_.profile ('AppData\Local\'+$relative+'\'+$name)})
            if ($entry.LinkType -ne 'Junction' -or [IO.Path]::GetFullPath([string]$entry.Target) -notin $known) {throw 'Existing state is not a recognized participant junction.'}
            $previous[$name]=[IO.Path]::GetFullPath([string]$entry.Target)
        }
    }
    if ($CheckOnly) {Write-Host 'CHECK_ONLY_PASS: no writes, credentials or app launch.';return}
    [void][IO.Directory]::CreateDirectory($control)
    try {$lease=[IO.File]::Open((Join-Path $control 'shared-home.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)}
    catch {throw 'Another shared launcher is active; do not delete the lock file.'}
    Assert-Stopped
    # Link metadata must be revalidated after obtaining the cross-user lease.
    foreach ($name in $targets.Keys) {
        $entry=Get-Item -LiteralPath (Join-Path $home $name) -Force -ErrorAction SilentlyContinue
        if ($previous[$name]) {
            if ($null -eq $entry -or $entry.LinkType -ne 'Junction' -or [IO.Path]::GetFullPath([string]$entry.Target) -ne $previous[$name]) {throw 'State link changed before lease acquisition.'}
        } elseif ($null -ne $entry) {throw 'State link appeared before lease acquisition.'}
    }
    foreach ($name in $targets.Keys) {
        Assert-ExistingAncestors $targets[$name]
        foreach ($parent in @((Join-Path $env:LOCALAPPDATA ($relative -split '[\\/]')[0]),$privateBase,$targets[$name])) {
            if (Test-Path -LiteralPath $parent) {Assert-Ordinary $parent}
            else {[void][IO.Directory]::CreateDirectory($parent)}
        }
    }
    try {
        foreach ($name in $targets.Keys) {
            if ($previous[$name] -eq $targets[$name]) {continue}
            $link=Join-Path $home $name
            if ($previous[$name]) {Remove-KnownLink $link $previous[$name]}
            $changed.Add($name)
            [void](New-Item -ItemType Junction -Path $link -Target $targets[$name] -ErrorAction Stop)
        }
    } catch {
        for ($i=$changed.Count-1;$i -ge 0;$i--) {
            $name=$changed[$i];$link=Join-Path $home $name
            $entry=Get-Item -LiteralPath $link -Force -ErrorAction SilentlyContinue
            if ($null -ne $entry) {Remove-KnownLink $link $targets[$name]}
            if ($previous[$name]) {[void](New-Item -ItemType Junction -Path $link -Target $previous[$name])}
        }
        throw
    }
    $oldPythonPath=$env:PYTHONPATH
    try {
        $env:PYTHONPATH=Join-Path (Split-Path -Parent $PSScriptRoot) 'src'
        & $python -B -X utf8 -m codex_shared_home.cli --settings $settingsPath prepare-config --profile $env:USERPROFILE --apply
        if ($LASTEXITCODE -ne 0) {throw 'Config preparation failed; app not started.'}
    } finally {$env:PYTHONPATH=$oldPythonPath}
    $start=[Diagnostics.ProcessStartInfo]::new()
    $start.FileName=$app
    $start.WorkingDirectory=Split-Path -Parent $app
    $start.UseShellExecute=$false
    foreach ($name in @($start.Environment.Keys | Where-Object {$_ -match '(?i)(TOKEN|SECRET|PASSWORD|COOKIE|AUTHORIZATION|API_KEY|APIKEY|PRIVATE_KEY|ACCESS_KEY)'})) {[void]$start.Environment.Remove($name)}
    $start.Environment['CODEX_HOME']=$home
    [void]$start.Environment.Remove('CODEX_SQLITE_HOME')
    $start.Environment['CODEX_ELECTRON_USER_DATA_PATH']=Join-Path $privateBase 'electron'
    if ($cfg.proxy_url) {
        $proxy=[uri][string]$cfg.proxy_url
        if ($proxy.Scheme -notin @('http','https') -or $proxy.UserInfo) {throw 'Use a credential-free HTTP proxy URI.'}
        $start.ArgumentList.Add('--proxy-server='+[string]$cfg.proxy_url)
        foreach ($name in @('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY')) {$start.Environment[$name]=[string]$cfg.proxy_url}
        $start.Environment['NO_PROXY']='localhost,127.0.0.1,::1'
    }
    $ownedApp=[Diagnostics.Process]::Start($start)
    $window=$false
    for ($attempt=0;$attempt -lt 150;$attempt++) {
        Start-Sleep -Seconds 1
        if (Test-Path -LiteralPath (Join-Path $home 'auth.json')) {throw 'Unexpected shared auth.json.'}
        $ownedApp.Refresh()
        if ($ownedApp.HasExited) {throw 'App exited before a window appeared.'}
        if ($ownedApp.MainWindowHandle -ne 0) {$window=$true;break}
    }
    if (-not $window) {throw 'No main window within 150 seconds.'}
    Write-Host 'Shared app opened. Sign in manually if needed. This is not login or sandbox acceptance.'
    while (-not $ownedApp.WaitForExit(1000)) {
        if (Test-Path -LiteralPath (Join-Path $home 'auth.json')) {throw 'Unexpected shared auth.json.'}
    }
} catch {
    if ($null -ne $ownedApp) {
        $ownedApp.Refresh()
        if (-not $ownedApp.HasExited) {$ownedApp.Kill($true);[void]$ownedApp.WaitForExit(5000)}
    }
    throw
} finally {
    if ($null -ne $lease) {$lease.Dispose()}
}
