# vhs script for the demo GIF: `vhs docs/demo.tape` writes docs/public/demo.gif
#
# Prerequisites:
#   * vhs (https://github.com/charmbracelet/vhs) and its ttyd/ffmpeg dependencies
#   * run from the REPO ROOT, not from docs/
#   * npm run build
#   * network access to the public OpenStreetMap services — no environment
#     variables are needed, the defaults are the public services and every tool
#     is read-only. The server rate-limits itself to ~1 request/second, so the
#     recording budget below is generous on purpose.
#
# Three beats: how many tools ship without any credentials, a geocode, and the
# same route on foot vs. by car — several times slower on foot, which is the
# FOSSGIS routed-* prefix correctness the server exists for. Inside a Hide block
# use vhs's own Sleep — the shell's `sleep` blocks the tape and the recording
# ends before any output appears.

Output docs/public/demo.gif

Set Shell "bash"
Set FontSize 17
Set Width 1260
Set Height 400
Set Padding 22
Set Theme "Catppuccin Mocha"
Set TypingSpeed 28ms

Hide
Type "clear" Enter
Sleep 400ms
Show

Type "node docs/demo.mjs"
Sleep 700ms
Enter
Sleep 14s
