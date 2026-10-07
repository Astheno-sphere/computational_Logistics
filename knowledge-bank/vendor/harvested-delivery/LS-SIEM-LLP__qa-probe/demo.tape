# qa-probe demo recording (VHS - https://github.com/charmbracelet/vhs)
#
# Records a short terminal GIF of qa-probe's report output.
#
# Prereqs:
#   1. Install VHS (one-time): see https://github.com/charmbracelet/vhs#installation
#        Windows:  winget install charmbracelet.vhs
#        macOS:    brew install vhs
#   2. Have a .qaprobe/ cache from a previous `qa-probe run` (so `report` renders instantly).
#
# Generate the GIF:
#   vhs demo.tape        ->  produces demo.gif
#
# Then add it to the top of README.md:
#   ![qa-probe demo](demo.gif)

Output demo.gif

Set FontSize 16
Set Width 1200
Set Height 760
Set Theme "Dracula"
Set Padding 18

Type "qa-probe report"
Sleep 600ms
Enter
Sleep 4s
