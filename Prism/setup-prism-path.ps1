$ErrorActionPreference = "Stop"

$prismDirectory = $PSScriptRoot.TrimEnd('\')
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$pathEntries = @($userPath -split ';' | Where-Object { $_.Trim() })

if (-not ($pathEntries | Where-Object { $_.TrimEnd('\') -ieq $prismDirectory })) {
    $updatedPath = if ([string]::IsNullOrWhiteSpace($userPath)) {
        $prismDirectory
    } else {
        "$($userPath.TrimEnd(';'));$prismDirectory"
    }
    [Environment]::SetEnvironmentVariable("Path", $updatedPath, "User")
    Write-Output "Added Prism to your user PATH: $prismDirectory"
} else {
    Write-Output "Prism is already on your user PATH: $prismDirectory"
}

Write-Output "Open a new Command Prompt, then run: pr-install WC"
