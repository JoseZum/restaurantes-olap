# Guía Completa del Sistema de Rutas de Entrega con Datos CSV

## 🎯 Descripción General

Este sistema de rutas de entrega integra **datos reales** desde archivos CSV con un motor de optimización de rutas basado en OpenStreetMap. El sistema carga automáticamente usuarios, restaurantes y pedidos desde los archivos CSV del proyecto y genera repartidores inteligentes para simular un sistema de delivery completo.

## 📊 Fuentes de Datos

### Datos CSV Reales
- **`usuarios.csv`**: ~8,000 usuarios (filtra solo clientes)
- **`restaurantes.csv`**: ~200 restaurantes con coordenadas reales de Costa Rica
- **`pedidos.csv`**: ~30,000 pedidos históricos (filtra PENDING/READY)

### Datos Generados Automáticamente
- **Repartidores**: 25 repartidores con nombres reales y ubicaciones OSM
- **Coordenadas de clientes**: Generadas basándose en calles reales del mapa OSM
- **Rutas**: Calculadas usando algoritmos de grafos (Dijkstra, TSP)

## 🚀 Inicio Rápido

### 1. Iniciar el Sistema

```bash
# Navegar al directorio del proyecto
cd restaurantes-olap/neo4j

# Ejecutar el API
python rutas_api/delivery_api.py
```

### 2. Cargar Datos CSV

```bash
# Usando curl
curl -X POST http://localhost:8000/csv/cargar

# Usando PowerShell
Invoke-RestMethod -Uri "http://localhost:8000/csv/cargar" -Method POST
```

### 3. Verificar Carga

```bash
# Ver estadísticas completas
curl http://localhost:8000/estadisticas/completas

# Ver restaurantes cargados
curl http://localhost:8000/restaurantes
```

## 📋 Endpoints Principales

### 🔄 Carga de Datos

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/csv/cargar` | POST | Cargar datos reales desde CSV |
| `/demo/inicializar` | POST | Cargar datos de demostración |
| `/estadisticas/completas` | GET | Ver estadísticas de datos cargados |

### 🍽️ Gestión de Restaurantes

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/restaurantes` | GET | Listar todos los restaurantes |
| `/restaurantes/{id}` | GET | Obtener restaurante específico |

### 👥 Gestión de Entidades

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/clientes` | GET/POST | Gestionar clientes |
| `/repartidores` | GET/POST | Gestionar repartidores |
| `/pedidos` | GET/POST | Gestionar pedidos |

### 🗺️ Optimización de Rutas

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/rutas/calcular` | POST | Calcular ruta óptima |
| `/asignar-pedidos` | POST | Asignación automática |

### 📊 Monitoreo

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/estado-sistema` | GET | Estado general del sistema |
| `/health` | GET | Health check |
| `/info` | GET | Información de la API |

## 🧪 Pruebas Automatizadas

### Ejecutar Pruebas Completas

```powershell
# Ejecutar script de pruebas completo
.\PRUEBA_SISTEMA_CSV_COMPLETO.ps1
```

### Pruebas Manuales Paso a Paso

#### 1. Verificar API
```bash
curl http://localhost:8000/health
curl http://localhost:8000/info
```

#### 2. Cargar Datos CSV
```bash
curl -X POST http://localhost:8000/csv/cargar
```

#### 3. Explorar Datos Cargados
```bash
# Ver restaurantes
curl http://localhost:8000/restaurantes

# Ver clientes
curl http://localhost:8000/clientes

# Ver repartidores
curl http://localhost:8000/repartidores

# Ver pedidos
curl http://localhost:8000/pedidos
```

#### 4. Probar Funcionalidades

**Asignar Pedidos Automáticamente:**
```bash
curl -X POST http://localhost:8000/asignar-pedidos
```

**Calcular Ruta Óptima:**
```bash
curl -X POST http://localhost:8000/rutas/calcular \
  -H "Content-Type: application/json" \
  -d '{
    "origen_lat": 9.8644,
    "origen_lon": -83.9194,
    "destinos": [
      {"lat": 9.8650, "lon": -83.9200},
      {"lat": 9.8660, "lon": -83.9180},
      {"lat": 9.8635, "lon": -83.9210}
    ]
  }'
```

## 📈 Ejemplos de Respuestas

### Carga de Datos CSV
```json
{
  "status": "success",
  "message": "Datos CSV cargados exitosamente",
  "datos_cargados": {
    "clientes_registrados": 89,
    "repartidores_activos": 25,
    "pedidos_pendientes": 156,
    "pedidos_en_ruta": 0,
    "rutas_activas": 0
  },
  "fuente": "CSV reales (usuarios.csv, restaurantes.csv, pedidos.csv)",
  "descripcion": "Sistema cargado con datos reales de usuarios clientes, restaurantes con coordenadas OSM y pedidos históricos"
}
```

### Lista de Restaurantes
```json
{
  "status": "success",
  "restaurantes": [
    {
      "id": 1,
      "nombre": "Solorio S.A.",
      "direccion": "Periférico Norte Chapa 970 Interior 688, Cartago, CR",
      "telefono": "1-023-516-4319x8045",
      "capacidad": 76,
      "categoria": "casual",
      "lat": 9.861415,
      "lon": -83.92935
    }
  ],
  "total_mostrados": 50,
  "mensaje": "Lista de restaurantes disponibles en el sistema"
}
```

### Asignación de Pedidos
```json
{
  "status": "success",
  "message": "Asignación automática completada",
  "asignaciones": {
    "1": [4, 26, 30],
    "2": [10, 19, 29],
    "3": [15, 22, 33]
  },
  "pedidos_asignados": 9
}
```

### Ruta Óptima
```json
{
  "status": "success",
  "ruta": {
    "distancia_total": 2847.5,
    "tiempo_total": 18,
    "secuencia_entregas": [
      [1, 9.8650, -83.9200],
      [2, 9.8635, -83.9210],
      [3, 9.8660, -83.9180]
    ],
    "coordenadas_ruta": [
      [9.8644, -83.9194],
      [9.8650, -83.9200],
      [9.8635, -83.9210],
      [9.8660, -83.9180]
    ]
  }
}
```

## 🔧 Configuración Avanzada

### Variables de Entorno
```bash
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="restaurantes123"
```

### Parámetros de Carga CSV
El sistema permite configurar la cantidad de datos a cargar:

```python
# En csv_data_loader.py
loader.cargar_todos_los_datos(
    max_usuarios=150,      # Número máximo de usuarios clientes
    max_pedidos=500,       # Número máximo de pedidos activos
    num_repartidores=25    # Número de repartidores a generar
)
```

## 🎯 Casos de Uso

### 1. Simulación de Delivery Real
```bash
# 1. Cargar datos reales
curl -X POST http://localhost:8000/csv/cargar

# 2. Asignar pedidos automáticamente
curl -X POST http://localhost:8000/asignar-pedidos

# 3. Ver estado del sistema
curl http://localhost:8000/estado-sistema
```

### 2. Análisis de Restaurantes
```bash
# Ver todos los restaurantes
curl http://localhost:8000/restaurantes

# Obtener detalle de restaurante específico
curl http://localhost:8000/restaurantes/1
```

### 3. Optimización de Rutas
```bash
# Calcular ruta para múltiples entregas
curl -X POST http://localhost:8000/rutas/calcular \
  -H "Content-Type: application/json" \
  -d '{"origen_lat": 9.8644, "origen_lon": -83.9194, "destinos": [...]}'
```

## 📊 Datos Estadísticos

### Volumen de Datos Típico
- **Clientes**: ~150 usuarios reales filtrados
- **Restaurantes**: ~200 establecimientos con coordenadas reales
- **Pedidos**: ~500 pedidos activos (PENDING/READY)
- **Repartidores**: 25 repartidores generados automáticamente
- **Calles OSM**: ~1,000 calles de Cartago, Costa Rica

### Rendimiento
- **Carga inicial**: ~10-15 segundos
- **Asignación de pedidos**: ~2-3 segundos
- **Cálculo de ruta**: ~1-2 segundos
- **Consultas**: <200ms promedio

## 🐛 Solución de Problemas

### Error: "Archivo no encontrado"
```bash
# Verificar que los archivos CSV existan
ls -la restaurantes-olap/spark/data/
```

### Error: "Sistema no inicializado"
```bash
# Cargar datos primero
curl -X POST http://localhost:8000/csv/cargar
```

### Error de conexión Neo4j
```bash
# Verificar que Neo4j esté ejecutándose
docker ps | grep neo4j

# Verificar credenciales
curl http://localhost:7474
```

### API no responde
```bash
# Verificar que el API esté ejecutándose
netstat -an | grep 8000

# Reiniciar el API
python rutas_api/delivery_api.py
```

## 🔗 Enlaces Útiles

- **Documentación Swagger**: http://localhost:8000/docs
- **API Info**: http://localhost:8000/info
- **Health Check**: http://localhost:8000/health
- **Estadísticas**: http://localhost:8000/estadisticas/completas
- **Restaurantes**: http://localhost:8000/restaurantes

## 🎉 Características Destacadas

### ✅ Datos Reales
- Usuarios reales del CSV de la base de datos
- Restaurantes con ubicaciones geográficas reales de Costa Rica
- Pedidos históricos reales para simulación

### ✅ Inteligencia Geográfica
- Coordenadas generadas basándose en calles OSM reales
- Algoritmos de optimización de rutas
- Cálculo de distancias y tiempos realistas

### ✅ Escalabilidad
- Sistema modular y extensible
- API REST completa
- Pruebas automatizadas

### ✅ Monitoreo
- Estadísticas detalladas en tiempo real
- Health checks automáticos
- Logging completo

## 🚀 Próximos Pasos

1. **Ejecutar las pruebas**: `.\PRUEBA_SISTEMA_CSV_COMPLETO.ps1`
2. **Explorar la API**: http://localhost:8000/docs
3. **Cargar datos CSV**: `POST /csv/cargar`
4. **Experimentar con rutas**: `POST /rutas/calcular`
5. **Monitorear el sistema**: `GET /estadisticas/completas`

¡El sistema está listo para usar con datos reales! 🎯 