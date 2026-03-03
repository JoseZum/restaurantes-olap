@echo off
echo ========================================
echo   SISTEMA DE RECOMENDACIONES SIMPLE
echo ========================================
echo.

cd /d "%~dp0"
cd scripts

echo Ejecutando configuracion del sistema de recomendaciones...
echo.
python setup_recommendations.py

echo.
echo ========================================
echo Ejecutando pruebas del sistema...
echo ========================================
echo.
python test_recommendations.py

echo.
echo ========================================
echo SISTEMA DE RECOMENDACIONES COMPLETO
echo ========================================
echo.
echo Presiona cualquier tecla para continuar...
pause > nul 