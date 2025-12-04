@echo off
setlocal enabledelayedexpansion

echo ======================================================================
echo Building unluac JAR
echo ======================================================================
echo.

REM Check if Java is installed
where javac >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: javac not found!
    echo Please install Java JDK and add it to PATH
    pause
    exit /b 1
)

where jar >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: jar not found!
    echo Please install Java JDK and add it to PATH
    pause
    exit /b 1
)

echo [1/5] Cleaning previous build...
if exist build (
    rmdir /s /q build
    echo     Removed build directory
)
if exist unluac.jar (
    del unluac.jar
    echo     Removed old JAR
)
if exist sources.txt (
    del sources.txt
)
echo.

echo [2/5] Creating build directory...
mkdir build
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to create build directory
    pause
    exit /b 1
)
echo     Created: build\
echo.

echo [3/5] Finding all Java source files...
REM Find all .java files and put them in a list
dir /s /b src\*.java > sources.txt

REM Count files
for /f %%A in ('type sources.txt ^| find /c /v ""') do set count=%%A
echo     Found %count% Java files
echo.

echo [4/5] Compiling Java source files...
echo     This may take a moment...
echo.

REM Compile using file list
javac -d build @sources.txt

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Compilation failed!
    echo Check the error messages above
    del sources.txt
    pause
    exit /b 1
)

echo     Compilation successful!
del sources.txt
echo.

echo [5/5] Creating JAR file...
cd build

REM Create JAR with Main-Class manifest
jar cvfe ..\unluac.jar unluac.Main . >nul 2>&1

cd ..

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: JAR creation failed!
    pause
    exit /b 1
)

if not exist unluac.jar (
    echo ERROR: unluac.jar was not created
    pause
    exit /b 1
)

echo     Created: unluac.jar
echo.

REM Get JAR file size
for %%I in (unluac.jar) do set size=%%~zI

echo ======================================================================
echo BUILD SUCCESSFUL!
echo ======================================================================
echo JAR file: unluac.jar
echo Size:     %size% bytes
echo.
echo Usage:    java -jar unluac.jar input.luac ^> output.lua
echo ======================================================================
echo.

REM Ask if user wants to test
set /p test="Test the JAR now? (y/n): "
if /i "%test%"=="y" (
    echo.
    echo Testing JAR...
    java -jar unluac.jar
    echo.
)

pause