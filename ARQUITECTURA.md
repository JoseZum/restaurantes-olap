# Arquitectura Detallada - Sistema OLAP de Restaurantes

## Índice
- [Arquitectura General](#arquitectura-general)
- [Modelo de Datos OLAP](#modelo-de-datos-olap)
- [Modelo de Grafos Neo4j](#modelo-de-grafos-neo4j)
- [Flujo de Datos ETL](#flujo-de-datos-etl)
- [Stack Tecnológico](#stack-tecnológico)

---

## Arquitectura General

### Componentes del Sistema

```mermaid
graph TB
    subgraph "CAPA DE PRESENTACIÓN"
        UI_SUPERSET["Superset UI<br/>Dashboards Interactivos<br/>:8088"]
        UI_AIRFLOW["Airflow UI<br/>Monitoreo Pipeline<br/>:8081"]
        UI_NEO4J["Neo4j Browser<br/>Exploración Grafo<br/>:7474"]
        UI_SPARK["Spark UI<br/>Jobs Monitor<br/>:6060"]
        UI_HDFS["HDFS UI<br/>Sistema Archivos<br/>:9870"]
    end

    subgraph "CAPA DE APLICACIÓN"
        AIRFLOW_SCHED["Airflow Scheduler<br/>Orquestación"]
        SUPERSET_APP["Superset App<br/>Query Engine"]
        NEO4J_CYPHER["Neo4j Cypher<br/>Query Processor"]
    end

    subgraph "CAPA DE PROCESAMIENTO"
        SPARK_MASTER["Spark Master<br/>Coordinador Cluster"]
        SPARK_WORKER["Spark Worker<br/>Executor"]

        subgraph "Jobs Spark"
            JOB_ETL["etl_from_csv.py<br/>ETL Principal"]
            JOB_TEND["tendencias_mejorado.py<br/>Análisis Temporal"]
            JOB_HOR["horarios_pico.py<br/>Análisis Horarios"]
            JOB_CREC["crecimiento.py<br/>Métricas Growth"]
        end
    end

    subgraph "CAPA DE ALMACENAMIENTO"
        subgraph "Data Warehouse"
            HDFS["HDFS<br/>Hadoop 3.2.1"]
            HIVE_META["Hive Metastore<br/>Catálogo Tablas"]
            HIVE_SERVER["HiveServer2<br/>SQL Interface"]
            PG_META[("PostgreSQL<br/>Metadata Hive")]

            subgraph "Tablas DW"
                HECHOS["hechos_reservas<br/>Fact Table"]
                DIM_TIEMPO["dim_tiempo"]
                DIM_USER["dim_usuario"]
                DIM_REST["dim_restaurante"]
                DIM_MENU["dim_menu"]
            end
        end

        subgraph "Base de Grafos"
            NEO4J_DB["Neo4j Database<br/>Graph Storage"]
            NEO4J_NODES["Nodos:<br/>Usuario, Restaurante,<br/>Producto, Pedido,<br/>Calle (OSM)"]
        end

        subgraph "Motor de Búsqueda"
            ELASTIC["Elasticsearch<br/>Índice Productos"]
        end
    end

    subgraph "CAPA DE DATOS"
        CSV_FILES["CSV Files<br/>8 archivos"]
        OSM_DATA["OpenStreetMap<br/>Cartago, CR"]
    end

    subgraph "BASES DE DATOS AUXILIARES"
        PG_AIRFLOW[("PostgreSQL<br/>Metadata Airflow<br/>:5434")]
        PG_SUPERSET[("PostgreSQL<br/>Metadata Superset<br/>:5435")]
        REDIS["Redis<br/>Cache Superset"]
    end

    CSV_FILES --> AIRFLOW_SCHED
    AIRFLOW_SCHED --> SPARK_MASTER
    SPARK_MASTER --> SPARK_WORKER
    SPARK_WORKER --> JOB_ETL
    SPARK_WORKER --> JOB_TEND
    SPARK_WORKER --> JOB_HOR
    SPARK_WORKER --> JOB_CREC

    JOB_ETL --> HDFS
    JOB_ETL --> HIVE_SERVER
    JOB_TEND --> HIVE_SERVER
    JOB_HOR --> HIVE_SERVER
    JOB_CREC --> HIVE_SERVER
    JOB_ETL --> ELASTIC

    HIVE_SERVER --> HIVE_META
    HIVE_META --> PG_META
    HDFS --> HECHOS
    HDFS --> DIM_TIEMPO
    HDFS --> DIM_USER
    HDFS --> DIM_REST
    HDFS --> DIM_MENU

    CSV_FILES --> NEO4J_CYPHER
    OSM_DATA --> NEO4J_CYPHER
    NEO4J_CYPHER --> NEO4J_DB
    NEO4J_DB --> NEO4J_NODES

    HIVE_SERVER --> SUPERSET_APP
    SUPERSET_APP --> PG_SUPERSET
    SUPERSET_APP --> REDIS

    AIRFLOW_SCHED --> PG_AIRFLOW

    UI_SUPERSET -.-> SUPERSET_APP
    UI_AIRFLOW -.-> AIRFLOW_SCHED
    UI_NEO4J -.-> NEO4J_CYPHER
    UI_SPARK -.-> SPARK_MASTER
    UI_HDFS -.-> HDFS
```

---

## Modelo de Datos OLAP

### Esquema Estrella - Data Warehouse

```mermaid
erDiagram
    hechos_reservas {
        int tiempo_id FK
        int usuario_id FK
        int restaurante_id FK
        int menu_id FK
        double total
        string estado_reserva
        string estado_pedido
        int invitados
    }

    dim_tiempo {
        int tiempo_id PK
        date fecha
        int ano
        int mes
        int dia
        int hora
        string nombre_mes_completo
        string dia_semana
    }

    dim_usuario {
        int usuario_id PK
        string email
        string rol
        timestamp fecha_alta
    }

    dim_restaurante {
        int restaurante_id PK
        string nombre
        string categoria
        int capacidad
        double lat
        double lon
    }

    dim_menu {
        int menu_id PK
        string titulo_menu
        string categoria_menu
        boolean activo
        int restaurante_id FK
    }

    hechos_reservas }o--|| dim_tiempo : "tiempo_id"
    hechos_reservas }o--|| dim_usuario : "usuario_id"
    hechos_reservas }o--|| dim_restaurante : "restaurante_id"
    hechos_reservas }o--|| dim_menu : "menu_id"
    dim_menu }o--|| dim_restaurante : "restaurante_id"
```

### Cubos OLAP (Vistas Agregadas)

```mermaid
graph LR
    HECHOS["hechos_reservas<br/>Tabla de Hechos"]

    subgraph "Cubos Analíticos"
        CUBO1["cubo_ingresos_mes_categoria<br/>Ingresos por tiempo y categoría"]
        CUBO2["cubo_actividad_geo<br/>Clientes por zona geográfica"]
        CUBO3["cubo_estado_pedido_mes<br/>Estados por periodo"]
        CUBO4["cubo_frecuencia_menu<br/>Productos más pedidos"]
        CUBO5["cubo_usuarios_ingresos<br/>Valor de cliente CLV"]
    end

    subgraph "Tablas de Análisis"
        TEND["dw_tendencias_consumo<br/>Tendencias temporales"]
        HOR["dw_horarios_pico<br/>Patrones horarios"]
        CREC["dw_crecimiento_mensual<br/>Métricas de crecimiento"]
    end

    HECHOS --> CUBO1
    HECHOS --> CUBO2
    HECHOS --> CUBO3
    HECHOS --> CUBO4
    HECHOS --> CUBO5

    HECHOS --> TEND
    HECHOS --> HOR
    HECHOS --> CREC
```

---

## Modelo de Grafos Neo4j

### Modelo Entidad-Relación de Grafos

```mermaid
graph LR
    subgraph "Nodos de Negocio"
        U["Usuario<br/>{id, email, rol,<br/>fecha_alta}"]
        R["Restaurante<br/>{id, nombre,<br/>categoria, lat, lon}"]
        PR["Producto<br/>{id, titulo,<br/>categoria, activo}"]
        P["Pedido<br/>{id, total,<br/>estado, fecha}"]
    end

    subgraph "Nodos de Red Vial (OSM)"
        C1["Calle<br/>{osm_id, lat, lon}"]
        C2["Calle<br/>{osm_id, lat, lon}"]
        C3["Calle<br/>{osm_id, lat, lon}"]
    end

    U -->|"REALIZO"| P
    U -->|"RESERVO"| R
    P -->|"EN_RESTAURANTE"| R
    P -->|"INCLUYE"| PR
    P -->|"INCLUYE_DETALLE<br/>{cantidad,<br/>precio_unitario,<br/>subtotal}"| PR
    R -->|"CERCA_DE<br/>{distancia: 0}"| C1
    C1 -->|"ROAD<br/>{distancia: metros}"| C2
    C2 -->|"ROAD<br/>{distancia: metros}"| C3
    C3 -->|"ROAD<br/>{distancia: metros}"| C1

    style U fill:#e1f5ff
    style R fill:#ffe1f5
    style PR fill:#fff4e1
    style P fill:#e1ffe1
    style C1 fill:#f5e1ff
    style C2 fill:#f5e1ff
    style C3 fill:#f5e1ff
```

### Algoritmos de Grafos Implementados

```mermaid
graph TB
    subgraph "Algoritmos APOC"
        DIJKSTRA["Dijkstra<br/>Ruta más corta<br/>entre restaurantes"]
        PAGERANK["PageRank<br/>Importancia de nodos"]
    end

    subgraph "Algoritmos GDS"
        COMMUNITY["Community Detection<br/>Agrupación de clientes"]
        SIMILARITY["Similarity<br/>Productos similares"]
    end

    subgraph "Análisis Custom"
        COCOMPRA["Co-Purchase Analysis<br/>Productos pedidos juntos"]
        RECOM["Recomendaciones<br/>Basadas en grafo"]
    end

    NEO4J[("Neo4j Database<br/>33k nodos viales<br/>+<br/>Nodos de negocio")]

    NEO4J --> DIJKSTRA
    NEO4J --> PAGERANK
    NEO4J --> COMMUNITY
    NEO4J --> SIMILARITY
    NEO4J --> COCOMPRA
    NEO4J --> RECOM

    DIJKSTRA --> ROUTES["Mapas HTML<br/>Leaflet.js"]
    COCOMPRA --> INSIGHTS["Insights de<br/>Análisis"]
```

---

## Flujo de Datos ETL

### Pipeline Completo

```mermaid
sequenceDiagram
    participant CSV as CSV Files
    participant AIRFLOW as Airflow Scheduler
    participant SPARK as Spark Cluster
    participant HDFS as HDFS
    participant HIVE as Hive Metastore
    participant DW as Data Warehouse
    participant NEO4J as Neo4j
    participant ELASTIC as Elasticsearch
    participant SUPERSET as Superset

    Note over AIRFLOW: Schedule: Diario 2 AM

    AIRFLOW->>AIRFLOW: 1. Check PostgreSQL
    AIRFLOW->>HIVE: 2. Check Metastore
    AIRFLOW->>CSV: 3. Validate Source Data

    Note over CSV,SPARK: EXTRACCIÓN
    AIRFLOW->>CSV: 4. Extract to CSV
    CSV->>SPARK: Load CSVs

    Note over SPARK,DW: TRANSFORMACIÓN
    SPARK->>SPARK: 5. etl_from_csv.py
    activate SPARK
    SPARK->>SPARK: Clean & Transform
    SPARK->>SPARK: Create Dimensions
    SPARK->>SPARK: Generate dim_tiempo
    SPARK->>SPARK: Build Fact Table

    Note over SPARK,DW: CARGA
    SPARK->>HDFS: Write Parquet Files
    SPARK->>HIVE: Register Tables
    HIVE->>DW: Create Schema
    deactivate SPARK

    Note over SPARK,ELASTIC: ANÁLISIS PARALELO
    par Análisis en Paralelo
        SPARK->>DW: 6a. tendencias_mejorado.py
        SPARK->>DW: 6b. horarios_pico.py
        SPARK->>DW: 6c. crecimiento.py
        SPARK->>ELASTIC: 6d. Index Products
    end

    Note over CSV,NEO4J: CARGA GRAFO
    CSV->>NEO4J: init_graph.py
    CSV->>NEO4J: csv_data_loader.py
    NEO4J->>NEO4J: Create Nodes & Relationships
    NEO4J->>NEO4J: Load OSM Road Network
    NEO4J->>NEO4J: Create Indexes

    Note over DW,SUPERSET: VISUALIZACIÓN
    DW->>SUPERSET: Connect via HiveServer2
    SUPERSET->>SUPERSET: Build Dashboards

    AIRFLOW->>DW: 7. Validate DW Quality
    AIRFLOW->>AIRFLOW: 8. Send Notification
```

### Transformaciones de Datos

```mermaid
graph TB
    subgraph "CSV Sources"
        CSV_U["usuarios.csv<br/>8,001 registros"]
        CSV_R["restaurantes.csv<br/>201 registros"]
        CSV_M["menus.csv<br/>801 registros"]
        CSV_P["pedidos.csv<br/>15,000 registros"]
        CSV_RES["reservas.csv<br/>15,000 registros"]
    end

    subgraph "Transformaciones Spark"
        T1["Limpieza de datos<br/>Validación de tipos"]
        T2["Casting de columnas<br/>String → Int, Double"]
        T3["Generación timestamp<br/>fecha + hora → timestamp"]
        T4["Extracción temporal<br/>año, mes, día, hora"]
        T5["Joins entre tablas<br/>reservas + pedidos"]
        T6["Agregaciones<br/>SUM, COUNT, AVG"]
    end

    subgraph "Dimensiones"
        D1["dim_usuario"]
        D2["dim_restaurante"]
        D3["dim_menu"]
        D4["dim_tiempo"]
    end

    subgraph "Hechos"
        F1["hechos_reservas<br/>Grain: 1 reserva-pedido"]
    end

    subgraph "Tablas Analíticas"
        A1["dw_tendencias_consumo"]
        A2["dw_horarios_pico"]
        A3["dw_crecimiento_mensual"]
    end

    CSV_U --> T1
    CSV_R --> T1
    CSV_M --> T1
    CSV_P --> T1
    CSV_RES --> T1

    T1 --> T2
    T2 --> T3
    T3 --> T4
    T4 --> T5
    T5 --> D1
    T5 --> D2
    T5 --> D3
    T5 --> D4

    D1 --> F1
    D2 --> F1
    D3 --> F1
    D4 --> F1

    F1 --> T6
    T6 --> A1
    T6 --> A2
    T6 --> A3
```

---

## Stack Tecnológico

### Matriz de Componentes

| Componente | Versión | Puerto(s) | Propósito | Recursos |
|------------|---------|-----------|-----------|----------|
| **Apache Airflow** | 2.8.0 | 8081 | Orquestación pipeline ETL | 2 servicios |
| **Apache Spark** | 3.5.3 | 7077, 6060 | Procesamiento distribuido | 1 Master + 1 Worker<br/>6 cores, 18GB RAM |
| **Apache Hive** | 3.1.3 | 10000, 9083 | Data Warehouse SQL | Metastore + HiveServer2 |
| **Hadoop HDFS** | 3.2.1 | 9870, 9000 | Almacenamiento distribuido | NameNode + DataNode |
| **Neo4j** | 5.25.1 | 7474, 7687 | Base de datos de grafos | APOC + GDS plugins |
| **Elasticsearch** | 8.11.0 | 9200 | Motor de búsqueda | Single-node, 512MB heap |
| **Apache Superset** | 3.0.0 | 8088 | Dashboards y BI | Con Redis cache |
| **PostgreSQL** | 14 | 5433-5435 | Metadatos | 3 instancias |
| **Redis** | 7 | 6379 | Cache | Para Superset |

### Formato de Datos

```mermaid
graph LR
    subgraph "Fuente"
        CSV["CSV<br/>Texto plano"]
    end

    subgraph "Procesamiento"
        SPARK_DF["Spark DataFrame<br/>In-memory"]
    end

    subgraph "Almacenamiento"
        PARQUET["Parquet<br/>Columnar"]
        JSON_ES["JSON<br/>Documentos"]
        CYPHER_GRAPH["Property Graph<br/>Neo4j"]
    end

    CSV --> SPARK_DF
    SPARK_DF --> PARQUET
    SPARK_DF --> JSON_ES
    CSV --> CYPHER_GRAPH

    PARQUET -.->|"Metadata"| HIVE_META["Hive Metastore"]
```

### Comunicación entre Servicios

```mermaid
graph TB
    subgraph "Protocolos de Red"
        HTTP["HTTP/REST<br/>Superset, Elasticsearch<br/>Airflow, UIs"]
        THRIFT["Thrift<br/>Hive Metastore<br/>:9083"]
        JDBC["JDBC<br/>HiveServer2<br/>:10000"]
        BOLT["Bolt<br/>Neo4j<br/>:7687"]
        RPC["gRPC/RPC<br/>HDFS<br/>:9000"]
        SPARK_PROTO["Spark Protocol<br/>Master-Worker<br/>:7077"]
    end

    subgraph "Interfaces"
        WEB["Web UI<br/>Navegador"]
        CLI["CLI<br/>spark-submit,<br/>airflow"]
        PYTHON["Python Scripts<br/>PySpark, py4j"]
    end

    WEB --> HTTP
    CLI --> SPARK_PROTO
    PYTHON --> THRIFT
    PYTHON --> JDBC
    PYTHON --> BOLT

    style HTTP fill:#e1f5ff
    style THRIFT fill:#ffe1f5
    style JDBC fill:#fff4e1
    style BOLT fill:#e1ffe1
```

---

## Características Avanzadas

### 1. Optimización de Rutas con OpenStreetMap

- **Red vial real**: 33,000 nodos de Cartago, Costa Rica
- **Algoritmo**: Dijkstra (APOC)
- **Visualización**: Mapas Leaflet.js
- **Casos de uso**: Rutas de entrega, análisis de cobertura

### 2. Análisis de Co-Compras

- **Técnica**: Graph pattern matching en Neo4j
- **Query**: Productos pedidos juntos en mismo pedido
- **Aplicación**: Recomendaciones, bundling

### 3. Procesamiento Distribuido

- **Spark**: 6 cores, 18GB RAM
- **Paralelización**: Jobs independientes en paralelo
- **Optimización**: Broadcast joins, Parquet columnar

### 4. Pipeline Automatizado

- **Frecuencia**: Diario a las 2 AM
- **Reintentos**: 1 retry automático
- **Notificaciones**: Email en éxito/fallo
- **Validaciones**: Calidad de datos pre y post-carga

### 5. Multi-Modelo de Datos

- **OLAP**: Esquema estrella en Hive
- **Grafo**: Property graph en Neo4j
- **Búsqueda**: Índices invertidos en Elasticsearch
- **Integración**: Datos relacionados entre modelos

---

## Escalabilidad

### Horizontal Scaling

```mermaid
graph LR
    subgraph "Actual (1 nodo)"
        SPARK_W1["Spark Worker 1<br/>6 cores"]
        HDFS_DN1["HDFS DataNode 1"]
    end

    subgraph "Escalado (N nodos)"
        SPARK_W2["Spark Worker 2<br/>6 cores"]
        SPARK_W3["Spark Worker N<br/>6 cores"]
        HDFS_DN2["HDFS DataNode 2"]
        HDFS_DN3["HDFS DataNode N"]
    end

    SPARK_W1 -.->|"Add nodes"| SPARK_W2
    SPARK_W2 -.->|"..."| SPARK_W3
    HDFS_DN1 -.->|"Add nodes"| HDFS_DN2
    HDFS_DN2 -.->|"..."| HDFS_DN3
```

### Despliegue en Kubernetes

- **Manifiestos**: Disponibles en `k8s/`
- **Namespaces**: Aislamiento de recursos
- **Secrets**: Gestión de credenciales
- **Ingress**: Exposición de servicios
- **Kustomize**: Configuración multi-entorno

---

## Seguridad

### Autenticación

| Servicio | Método | Credenciales |
|----------|--------|--------------|
| Airflow | Basic Auth | admin / admin |
| Superset | Session-based | admin / admin |
| Neo4j | Native Auth | neo4j / restaurantes123 |
| PostgreSQL | Password | hive / hive123, etc. |

### Redes Docker

- **olapnet**: Red interna aislada
- **mongo-cluster**: Red externa (futura integración)
- Sin exposición directa de puertos críticos

---

## Monitoreo

### Interfaces de Administración

| UI | URL | Métricas |
|----|-----|----------|
| Airflow | :8081 | DAG runs, task duration, failures |
| Spark | :6060 | Jobs, stages, executors, storage |
| HDFS | :9870 | Datanodes, disk usage, replication |
| Superset | :8088 | Query performance, cache hit rate |
| Neo4j | :7474 | Query performance, store size |

---

## Conclusión

Esta arquitectura implementa un **stack completo de Big Data** con:

✅ Data Warehouse OLAP (esquema estrella)
✅ Procesamiento distribuido (Spark)
✅ Orquestación automatizada (Airflow)
✅ Análisis de grafos (Neo4j + OSM)
✅ Búsqueda full-text (Elasticsearch)
✅ Visualización avanzada (Superset)
✅ Despliegue containerizado (Docker + K8s)

**Capacidades analíticas**:
- OLAP multidimensional
- Optimización de rutas
- Recomendaciones basadas en grafos
- Análisis temporal y tendencias
- Métricas de negocio (CLV, churn, growth)
