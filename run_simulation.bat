@echo off
setlocal
echo ========================================================
echo   Compiling and Simulating Half & Full Adder (Verilog)
echo ========================================================

:: Ensure Icarus Verilog path is in current session
set "PATH=%LOCALAPPDATA%\iverilog\app\bin;%LOCALAPPDATA%\iverilog\app\gtkwave\bin;%PATH%"

echo 1. Compiling Verilog files with iverilog...
iverilog -o adders_sim.vvp half_adder.v full_adder.v tb_adders.v
if %errorlevel% neq 0 (
    echo [ERROR] Compilation failed!
    pause
    exit /b %errorlevel%
)

echo 2. Running simulation with vvp...
vvp adders_sim.vvp
if %errorlevel% neq 0 (
    echo [ERROR] Simulation execution failed!
    pause
    exit /b %errorlevel%
)

echo.
echo Simulation complete!
echo To view waveforms in GTKWave, run:
echo gtkwave adders.vcd
echo.
pause

