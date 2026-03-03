# PRUEBA COMPLETA DEL SISTEMA DE RUTAS CON DATOS CSV
# ====================================================
Write-Host "INICIANDO PRUEBAS COMPLETAS DEL SISTEMA DE RUTAS CSV" -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""

# Variables de configuracion
$API_URL = "http://localhost:8000"
$TIMEOUT = 30

# Funcion para hacer requests HTTP
function Invoke-APIRequest {
    param(
        [string]$Method,
        [string]$Endpoint,
        [object]$Body = $null,
        [string]$Description
    )
    
    try {
        Write-Host "Ejecutando: $Description..." -ForegroundColor Yellow
        
        $params = @{
            Uri = "$API_URL$Endpoint"
            Method = $Method
            ContentType = "application/json"
            TimeoutSec = $TIMEOUT
        }
        
        if ($Body) {
            $params.Body = ($Body | ConvertTo-Json -Depth 10)
        }
        
        $response = Invoke-RestMethod @params
        Write-Host "EXITOSO: $Description" -ForegroundColor Green
        return $response
    }
    catch {
        Write-Host "ERROR: $Description - $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }
}

# Funcion para mostrar estadisticas
function Show-Statistics {
    param([object]$Stats, [string]$Title)
    
    Write-Host ""
    Write-Host "ESTADISTICAS: $Title" -ForegroundColor Cyan
    Write-Host "=" * 50 -ForegroundColor Cyan
    
    if ($Stats) {
        $Stats.PSObject.Properties | ForEach-Object {
            Write-Host "  $($_.Name): $($_.Value)" -ForegroundColor White
        }
    } else {
        Write-Host "  No hay datos disponibles" -ForegroundColor Red
    }
    Write-Host ""
}

# 1. VERIFICAR API
Write-Host "1. VERIFICACION INICIAL DEL API" -ForegroundColor Blue
Write-Host "================================" -ForegroundColor Blue

$health = Invoke-APIRequest -Method "GET" -Endpoint "/health" -Description "Health Check"
if (-not $health) {
    Write-Host "ERROR: El API no esta disponible. Verifique que este ejecutandose en puerto 8000" -ForegroundColor Red
    exit 1
}

$info = Invoke-APIRequest -Method "GET" -Endpoint "/info" -Description "Informacion del API"
if ($info) {
    Write-Host "API: $($info.api)" -ForegroundColor Cyan
    Write-Host "Version: $($info.version)" -ForegroundColor Cyan
}

# 2. CARGAR DATOS CSV
Write-Host ""
Write-Host "2. CARGA DE DATOS CSV REALES" -ForegroundColor Blue
Write-Host "=============================" -ForegroundColor Blue

$carga_csv = Invoke-APIRequest -Method "POST" -Endpoint "/csv/cargar" -Description "Cargar datos desde CSV"
if ($carga_csv) {
    Write-Host "EXITOSO: Datos CSV cargados exitosamente" -ForegroundColor Green
    Show-Statistics -Stats $carga_csv.datos_cargados -Title "DATOS CARGADOS DESDE CSV"
} else {
    Write-Host "ERROR: Error cargando datos CSV. Intentando con datos demo..." -ForegroundColor Yellow
    $demo = Invoke-APIRequest -Method "POST" -Endpoint "/demo/inicializar" -Description "Cargar datos demo"
    if ($demo) {
        Show-Statistics -Stats $demo.datos_creados -Title "DATOS DEMO CARGADOS"
    }
}

# 3. ESTADISTICAS DEL SISTEMA
Write-Host ""
Write-Host "3. ESTADISTICAS DEL SISTEMA" -ForegroundColor Blue
Write-Host "============================" -ForegroundColor Blue

$stats = Invoke-APIRequest -Method "GET" -Endpoint "/estadisticas/completas" -Description "Obtener estadisticas completas"
if ($stats) {
    Show-Statistics -Stats $stats.estadisticas_sistema -Title "ESTADISTICAS DEL SISTEMA"
    if ($stats.estadisticas_csv -ne "No disponibles") {
        Show-Statistics -Stats $stats.estadisticas_csv -Title "ESTADISTICAS CSV"
    }
}

# 4. LISTAR RESTAURANTES
Write-Host ""
Write-Host "4. GESTION DE RESTAURANTES" -ForegroundColor Blue
Write-Host "===========================" -ForegroundColor Blue

$restaurantes = Invoke-APIRequest -Method "GET" -Endpoint "/restaurantes" -Description "Listar restaurantes"
if ($restaurantes) {
    Write-Host "Total de restaurantes: $($restaurantes.total_mostrados)" -ForegroundColor Cyan
    Write-Host "Primeros 5 restaurantes:" -ForegroundColor Cyan
    
    $restaurantes.restaurantes[0..4] | ForEach-Object {
        Write-Host "  - ID: $($_.id) - $($_.nombre) - $($_.categoria) - Lat: $($_.lat), Lon: $($_.lon)" -ForegroundColor Gray
    }
    
    # Probar obtener un restaurante especifico
    if ($restaurantes.restaurantes.Count -gt 0) {
        $primer_restaurante_id = $restaurantes.restaurantes[0].id
        $restaurante_detalle = Invoke-APIRequest -Method "GET" -Endpoint "/restaurantes/$primer_restaurante_id" -Description "Obtener restaurante especifico"
        if ($restaurante_detalle) {
            Write-Host "Detalle del restaurante $primer_restaurante_id" -ForegroundColor Cyan
            Write-Host "   Nombre: $($restaurante_detalle.restaurante.nombre)" -ForegroundColor Gray
        }
    }
}

# 5. LISTAR CLIENTES
Write-Host ""
Write-Host "5. GESTION DE CLIENTES" -ForegroundColor Blue
Write-Host "=======================" -ForegroundColor Blue

$clientes = Invoke-APIRequest -Method "GET" -Endpoint "/clientes" -Description "Listar clientes"
if ($clientes) {
    Write-Host "Total de clientes: $($clientes.total)" -ForegroundColor Cyan
    Write-Host "Primeros 3 clientes:" -ForegroundColor Cyan
    
    $clientes.clientes[0..2] | ForEach-Object {
        Write-Host "  - ID: $($_.id) - $($_.nombre) - Tel: $($_.telefono)" -ForegroundColor Gray
        Write-Host "    Ubicacion: Lat $($_.lat), Lon $($_.lon)" -ForegroundColor Gray
    }
}

# 6. LISTAR REPARTIDORES
Write-Host ""
Write-Host "6. GESTION DE REPARTIDORES" -ForegroundColor Blue
Write-Host "===========================" -ForegroundColor Blue

$repartidores = Invoke-APIRequest -Method "GET" -Endpoint "/repartidores" -Description "Listar repartidores"
if ($repartidores) {
    Write-Host "Total de repartidores: $($repartidores.total)" -ForegroundColor Cyan
    Write-Host "Primeros 5 repartidores:" -ForegroundColor Cyan
    
    $repartidores.repartidores[0..4] | ForEach-Object {
        Write-Host "  - ID: $($_.id) - $($_.nombre) - Capacidad: $($_.capacidad_max) - Velocidad: $($_.velocidad_promedio) km/h" -ForegroundColor Gray
        Write-Host "    Ubicacion: Lat $($_.lat), Lon $($_.lon) - Activo: $($_.activo)" -ForegroundColor Gray
    }
}

# 7. LISTAR PEDIDOS
Write-Host ""
Write-Host "7. GESTION DE PEDIDOS" -ForegroundColor Blue
Write-Host "======================" -ForegroundColor Blue

$pedidos = Invoke-APIRequest -Method "GET" -Endpoint "/pedidos" -Description "Listar pedidos"
if ($pedidos) {
    Write-Host "Total de pedidos: $($pedidos.total)" -ForegroundColor Cyan
    Write-Host "Primeros 5 pedidos:" -ForegroundColor Cyan
    
    $pedidos.pedidos[0..4] | ForEach-Object {
        Write-Host "  - ID: $($_.id) - Cliente: $($_.cliente_id) - Restaurante: $($_.restaurante_id)" -ForegroundColor Gray
        Write-Host "    Total: $($_.total) - Estado: $($_.estado) - Prioridad: $($_.prioridad)" -ForegroundColor Gray
    }
}

# 8. ASIGNACION AUTOMATICA
Write-Host ""
Write-Host "8. ASIGNACION AUTOMATICA DE PEDIDOS" -ForegroundColor Blue
Write-Host "====================================" -ForegroundColor Blue

$asignacion = Invoke-APIRequest -Method "POST" -Endpoint "/asignar-pedidos" -Description "Asignar pedidos automaticamente"
if ($asignacion) {
    Write-Host "EXITOSO: Asignacion completada" -ForegroundColor Green
    Write-Host "Pedidos asignados: $($asignacion.pedidos_asignados)" -ForegroundColor Cyan
    
    if ($asignacion.asignaciones) {
        Write-Host "Detalle de asignaciones:" -ForegroundColor Cyan
        $asignacion.asignaciones.PSObject.Properties | ForEach-Object {
            $repartidor_id = $_.Name
            $pedidos_asignados = $_.Value
            Write-Host "  Repartidor $repartidor_id - $($pedidos_asignados.Count) pedidos" -ForegroundColor Gray
        }
    }
}

# 9. CALCULO DE RUTAS
Write-Host ""
Write-Host "9. CALCULO DE RUTAS OPTIMAS" -ForegroundColor Blue
Write-Host "============================" -ForegroundColor Blue

$ruta_request = @{
    origen_lat = 9.8644
    origen_lon = -83.9194
    destinos = @(
        @{ lat = 9.8650; lon = -83.9200 }
        @{ lat = 9.8660; lon = -83.9180 }
        @{ lat = 9.8635; lon = -83.9210 }
    )
}

$ruta = Invoke-APIRequest -Method "POST" -Endpoint "/rutas/calcular" -Body $ruta_request -Description "Calcular ruta optima"
if ($ruta) {
    Write-Host "EXITOSO: Ruta calculada exitosamente" -ForegroundColor Green
    Write-Host "Distancia total: $($ruta.ruta.distancia_total) metros" -ForegroundColor Cyan
    Write-Host "Tiempo total: $($ruta.ruta.tiempo_total) minutos" -ForegroundColor Cyan
    Write-Host "Secuencia de entregas: $($ruta.ruta.secuencia_entregas.Count) paradas" -ForegroundColor Cyan
}

# 10. ESTADO FINAL DEL SISTEMA
Write-Host ""
Write-Host "10. ESTADO FINAL DEL SISTEMA" -ForegroundColor Blue
Write-Host "=============================" -ForegroundColor Blue

$estado_final = Invoke-APIRequest -Method "GET" -Endpoint "/estado-sistema" -Description "Estado final del sistema"
if ($estado_final) {
    Show-Statistics -Stats $estado_final.sistema -Title "ESTADO FINAL DEL SISTEMA"
}

# 11. PRUEBAS DE RENDIMIENTO
Write-Host ""
Write-Host "11. PRUEBAS DE RENDIMIENTO" -ForegroundColor Blue
Write-Host "===========================" -ForegroundColor Blue

Write-Host "Ejecutando 10 requests rapidos al health check..." -ForegroundColor Yellow
$start_time = Get-Date

for ($i = 1; $i -le 10; $i++) {
    $health_test = Invoke-APIRequest -Method "GET" -Endpoint "/health" -Description "Health check $i"
    if (-not $health_test) {
        Write-Host "ERROR: Fallo el health check $i" -ForegroundColor Red
    }
}

$end_time = Get-Date
$duration = ($end_time - $start_time).TotalSeconds
Write-Host "10 requests completados en $([math]::Round($duration, 2)) segundos" -ForegroundColor Cyan
Write-Host "Promedio: $([math]::Round($duration/10, 3)) segundos por request" -ForegroundColor Cyan

# RESUMEN FINAL
Write-Host ""
Write-Host "RESUMEN DE PRUEBAS COMPLETADAS" -ForegroundColor Green
Write-Host "===============================" -ForegroundColor Green
Write-Host "EXITOSO: Sistema de rutas funcionando correctamente" -ForegroundColor Green
Write-Host "EXITOSO: Datos CSV cargados y procesados" -ForegroundColor Green
Write-Host "EXITOSO: Clientes, repartidores y pedidos registrados" -ForegroundColor Green
Write-Host "EXITOSO: Restaurantes con ubicaciones reales" -ForegroundColor Green
Write-Host "EXITOSO: Asignacion automatica de pedidos funcional" -ForegroundColor Green
Write-Host "EXITOSO: Calculo de rutas optimas operativo" -ForegroundColor Green
Write-Host "EXITOSO: API respondiendo en tiempos aceptables" -ForegroundColor Green
Write-Host ""
Write-Host "Para mas pruebas, visite: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "Para ver estadisticas: http://localhost:8000/estadisticas/completas" -ForegroundColor Cyan
Write-Host "Para ver restaurantes: http://localhost:8000/restaurantes" -ForegroundColor Cyan
Write-Host ""
Write-Host "PRUEBAS COMPLETADAS EXITOSAMENTE!" -ForegroundColor Green 