@echo off
rem 더블클릭하거나 cmd 에서 "tree.bat" 입력으로 실행
cd /d "%~dp0"
where py >nul 2>nul && (py -3 xmas_tree.py %* & goto :eof)
python xmas_tree.py %*
