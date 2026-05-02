# Shim: forwards to the standardized start_server.ps1.
# Kept so existing muscle memory / docs that reference run_server.ps1 still work.
# Safe to delete once nothing references this name.
& "$PSScriptRoot\start_server.ps1" @Args
