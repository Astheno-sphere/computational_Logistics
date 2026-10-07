; Extra running-process checks for NSIS install/uninstall.
; Tauri already checks the main app binary; also cover the MCP sidecar so
; File copy does not hang when an MCP client is holding unfour-mcp.exe.
;
; Prompt once, then retry-kill until no unfour-mcp.exe remains (MCP hosts can
; respawn the sidecar between a single KillProcess and the File copy).
!macro CheckAndKillUnfourMcp
  !define UnfourMcpCheckID ${__LINE__}

  nsis_tauri_utils::StrReplace "$(appRunning)" "{{product_name}}" "unfour-mcp"
  Pop $R1
  nsis_tauri_utils::StrReplace "$(appRunningOkKill)" "{{product_name}}" "unfour-mcp"
  Pop $R2
  nsis_tauri_utils::StrReplace "$(failedToKillApp)" "{{product_name}}" "unfour-mcp"
  Pop $R3

  !if "${INSTALLMODE}" == "currentUser"
    nsis_tauri_utils::FindProcessCurrentUser "unfour-mcp.exe"
  !else
    nsis_tauri_utils::FindProcess "unfour-mcp.exe"
  !endif
  Pop $R0
  ${If} $R0 = 0
    IfSilent unfour_mcp_kill_${UnfourMcpCheckID} 0
    ${IfThen} $PassiveMode != 1 ${|} MessageBox MB_OKCANCEL $R2 IDOK unfour_mcp_kill_${UnfourMcpCheckID} IDCANCEL unfour_mcp_cancel_${UnfourMcpCheckID} ${|}
    unfour_mcp_kill_${UnfourMcpCheckID}:
      StrCpy $R9 0
      unfour_mcp_kill_retry_${UnfourMcpCheckID}:
        !if "${INSTALLMODE}" == "currentUser"
          nsis_tauri_utils::KillProcessCurrentUser "unfour-mcp.exe"
        !else
          nsis_tauri_utils::KillProcess "unfour-mcp.exe"
        !endif
        Pop $R0
        Sleep 500
        !if "${INSTALLMODE}" == "currentUser"
          nsis_tauri_utils::FindProcessCurrentUser "unfour-mcp.exe"
        !else
          nsis_tauri_utils::FindProcess "unfour-mcp.exe"
        !endif
        Pop $R0
        ; FindProcess: 0 = still running, non-zero = gone
        ${If} $R0 != 0
          Goto unfour_mcp_done_${UnfourMcpCheckID}
        ${EndIf}
        IntOp $R9 $R9 + 1
        ${If} $R9 < 10
          Goto unfour_mcp_kill_retry_${UnfourMcpCheckID}
        ${EndIf}
        IfSilent unfour_mcp_silent_${UnfourMcpCheckID} unfour_mcp_ui_${UnfourMcpCheckID}
        unfour_mcp_silent_${UnfourMcpCheckID}:
          System::Call 'kernel32::AttachConsole(i -1)i.r0'
          ${If} $0 != 0
            System::Call 'kernel32::GetStdHandle(i -11)i.r0'
            System::call 'kernel32::SetConsoleTextAttribute(i r0, i 0x0004)'
            FileWrite $0 "$R1$\n"
          ${EndIf}
          Abort
        unfour_mcp_ui_${UnfourMcpCheckID}:
          Abort $R3
    unfour_mcp_cancel_${UnfourMcpCheckID}:
      Abort $R1
  ${EndIf}
  unfour_mcp_done_${UnfourMcpCheckID}:
  !undef UnfourMcpCheckID
!macroend

!macro NSIS_HOOK_PREINSTALL
  !insertmacro CheckAndKillUnfourMcp
!macroend
!macro NSIS_HOOK_PREUNINSTALL
  !insertmacro CheckAndKillUnfourMcp
!macroend
