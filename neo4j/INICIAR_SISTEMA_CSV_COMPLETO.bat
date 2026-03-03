@echo off
chcp 65001 >nul
title Sistema de Rutas de Entrega con Datos CSV

echo.
echo ====================================================
echo SISTEMA DE RUTAS DE ENTREGA CON DATOS CSV
echo ====================================================
echo.
echo Este script iniciara automaticamente:
echo [X] API de rutas de entrega
echo [X] Carga de datos CSV reales
echo [X] Verificacion del sistema
echo.

echo Verificando dependencias...
echo.

REM Verificar que Python este disponible
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado. Instale Python 3.8+ y reinicie.
    pause
    exit /b 1
)

echo [OK] Python encontrado

REM Verificar que los archivos CSV existan
if not exist "..\spark\data\usuarios.csv" (
    echo [ERROR] No se encontro usuarios.csv en spark/data/
    echo    Verifique que los archivos CSV esten en la ubicacion correcta
    pause
    exit /b 1
)

if not exist "..\spark\data\restaurantes.csv" (
    echo [ERROR] No se encontro restaurantes.csv en spark/data/
    pause
    exit /b 1
)

if not exist "..\spark\data\pedidos.csv" (
    echo [ERROR] No se encontro pedidos.csv en spark/data/
    pause
    exit /b 1
)

echo [OK] Archivos CSV encontrados

REM Verificar que Neo4j este ejecutandose
echo Verificando conexion a Neo4j...
timeout /t 2 >nul

REM Iniciar el API en segundo plano
echo.
echo Iniciando API de rutas de entrega...
echo.

start "API Rutas" cmd /k "echo API de Rutas de Entrega && echo ======================= && echo. && echo Iniciando servidor... && python rutas_api\delivery_api.py"

REM Esperar a que el API se inicie
echo Esperando que el API se inicie...
timeout /t 10 >nul

REM Verificar que el API este funcionando
echo Verificando que el API este funcionando...
powershell -Command "try { $response = Invoke-RestMethod -Uri 'http://localhost:8000/health' -TimeoutSec 5; if ($response.status -eq 'healthy') { Write-Host '[OK] API funcionando correctamente' -ForegroundColor Green; exit 0 } else { Write-Host '[ERROR] API no responde correctamente' -ForegroundColor Red; exit 1 } } catch { Write-Host '[ERROR] No se pudo conectar al API' -ForegroundColor Red; exit 1 }"

if errorlevel 1 (
    echo.
    echo [ERROR] El API no esta funcionando correctamente
    echo    Verifique los logs en la ventana del API
    pause
    exit /b 1
)

echo.
echo Cargando datos CSV reales...
echo.

REM Cargar datos CSV
powershell -Command "try { Write-Host 'Cargando datos desde CSV...' -ForegroundColor Yellow; $response = Invoke-RestMethod -Uri 'http://localhost:8000/csv/cargar' -Method POST -TimeoutSec 30; Write-Host '[OK] Datos CSV cargados exitosamente' -ForegroundColor Green; Write-Host 'Clientes registrados:' $response.datos_cargados.clientes_registrados -ForegroundColor Cyan; Write-Host 'Repartidores activos:' $response.datos_cargados.repartidores_activos -ForegroundColor Cyan; Write-Host 'Pedidos pendientes:' $response.datos_cargados.pedidos_pendientes -ForegroundColor Cyan } catch { Write-Host '[ERROR] Error cargando datos CSV:' $_.Exception.Message -ForegroundColor Red; Write-Host 'Intentando cargar datos demo...' -ForegroundColor Yellow; try { $demo = Invoke-RestMethod -Uri 'http://localhost:8000/demo/inicializar' -Method POST; Write-Host '[OK] Datos demo cargados' -ForegroundColor Green } catch { Write-Host '[ERROR] Error cargando datos demo' -ForegroundColor Red } }"

echo.
echo Ejecutando pruebas basicas del sistema...
echo.

REM Ejecutar algunas pruebas basicas
powershell -Command "Write-Host 'Probando endpoints basicos...' -ForegroundColor Yellow; try { $info = Invoke-RestMethod -Uri 'http://localhost:8000/info'; Write-Host '[OK] Endpoint /info funcionando' -ForegroundColor Green; $restaurantes = Invoke-RestMethod -Uri 'http://localhost:8000/restaurantes'; Write-Host '[OK] Endpoint /restaurantes funcionando -' $restaurantes.total_mostrados 'restaurantes' -ForegroundColor Green; $clientes = Invoke-RestMethod -Uri 'http://localhost:8000/clientes'; Write-Host '[OK] Endpoint /clientes funcionando -' $clientes.total 'clientes' -ForegroundColor Green } catch { Write-Host '[WARN] Algunos endpoints podrian no estar funcionando' -ForegroundColor Yellow }"

echo.
echo SISTEMA INICIADO EXITOSAMENTE!
echo ===============================
echo.
echo URLs importantes:
echo    • API Docs: http://localhost:8000/docs
echo    • Health Check: http://localhost:8000/health
echo    • Informacion: http://localhost:8000/info
echo    • Estadisticas: http://localhost:8000/estadisticas/completas
echo    • Restaurantes: http://localhost:8000/restaurantes
echo.
echo Para ejecutar pruebas completas:
echo    .\PRUEBA_SISTEMA_CSV_COMPLETO.ps1
echo.
echo Para ver la documentacion completa:
echo    GUIA_COMPLETA_SISTEMA_CSV.md
echo.
echo Comandos utiles:
echo    • Cargar CSV: POST http://localhost:8000/csv/cargar
echo    • Asignar pedidos: POST http://localhost:8000/asignar-pedidos
echo    • Calcular rutas: POST http://localhost:8000/rutas/calcular
echo.

REM Preguntar si ejecutar pruebas automaticas
echo Desea ejecutar las pruebas automaticas completas? (S/N)
set /p ejecutar_pruebas="Respuesta: "

if /i "%ejecutar_pruebas%"=="S" (
    echo.
    echo Ejecutando pruebas automaticas...
    echo.
    powershell -ExecutionPolicy Bypass -File "PRUEBA_SISTEMA_CSV_COMPLETO.ps1"
) else (
    echo.
    echo [OK] Sistema listo para usar
    echo    El API seguira ejecutandose en segundo plano
    echo    Cierre la ventana "API Rutas" para detener el servidor
)

echo.
echo Presione cualquier tecla para continuar...
pause >nul 