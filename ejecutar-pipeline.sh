#!/bin/bash

# Script para ejecutar el pipeline completo del proyecto OLAP

echo "=== EJECUTANDO PIPELINE COMPLETO OLAP ==="
echo ""

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Función para verificar éxito
check_success() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}$1 completado${NC}"
    else
        echo -e "${RED}Error en $1${NC}"
        exit 1
    fi
}

# 1. Verificar archivos necesarios
echo -e "${BLUE}1. Verificando archivos necesarios...${NC}"
if [ ! -f "drivers/postgresql-42.5.1.jar" ]; then
    echo "Descargando driver JDBC..."
    wget -q https://jdbc.postgresql.org/download/postgresql-42.5.1.jar -P drivers/
fi

# Verificar CSVs
CSV_COUNT=$(ls spark/data/*.csv 2>/dev/null | wc -l)
if [ $CSV_COUNT -eq 0 ]; then
    echo -e "${YELLOW}No hay CSVs en spark/data/. Copiando desde ../data/${NC}"
    cp ../data/*.csv spark/data/ 2>/dev/null || echo "No se encontraron CSVs para copiar"
fi

# 2. Detener servicios anteriores
echo -e "\n${BLUE}2. Limpiando servicios anteriores...${NC}"
docker-compose down
check_success "Limpieza"

# 3. Usar docker-compose con o sin Airflow
echo -e "\n${BLUE}3. ¿Deseas incluir Airflow? (s/n)${NC}"
read -p "> " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Ss]$ ]]; then
    COMPOSE_FILE="docker-compose-airflow.yml"
    INCLUDE_AIRFLOW=true
else
    COMPOSE_FILE="docker-compose.yml"
    INCLUDE_AIRFLOW=false
fi

# 4. Levantar servicios
echo -e "\n${BLUE}4. Levantando servicios con $COMPOSE_FILE...${NC}"
docker-compose -f $COMPOSE_FILE up -d
check_success "Docker Compose"

# 5. Esperar a que los servicios estén listos
echo -e "\n${BLUE}5. Esperando a que los servicios estén listos...${NC}"

echo -n "PostgreSQL Metastore"
for i in {1..30}; do
    if docker exec postgres-metastore pg_isready -U hive -d metastore &>/dev/null; then
        echo -e " ${GREEN}OK${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

echo -n "Hive Metastore"
for i in {1..60}; do
    if docker exec hive nc -z localhost 9083 2>/dev/null; then
        echo -e " ${GREEN}OK${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

echo -n "HiveServer2"
for i in {1..30}; do
    if docker exec hive nc -z localhost 10000 2>/dev/null; then
        echo -e " ${GREEN}OK${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

if [ "$INCLUDE_AIRFLOW" = true ]; then
    echo -n "Airflow"
    for i in {1..60}; do
        if curl -s http://localhost:8081/health | grep -q healthy; then
            echo -e " ${GREEN}OK${NC}"
            break
        fi
        echo -n "."
        sleep 3
    done
fi

# 6. Ejecutar ETL
echo -e "\n${BLUE}6. Ejecutando ETL desde CSVs...${NC}"
./run-spark-job.sh etl_from_csv.py
check_success "ETL"

# 7. Verificar datos cargados
echo -e "\n${BLUE}7. Verificando datos cargados...${NC}"
TOTAL=$(docker exec hive beeline -u jdbc:hive2://localhost:10000 --silent=true -e "USE restaurantes_dw; SELECT COUNT(*) FROM hechos_reservas;" 2>/dev/null | grep -E "[0-9]+" | head -1)
echo "Total registros en hechos_reservas: $TOTAL"

# 8. Ejecutar análisis
echo -e "\n${BLUE}8. Ejecutando análisis con Spark...${NC}"

echo "Ejecutando análisis de tendencias..."
./run-spark-job.sh tendencias.py
check_success "Análisis de tendencias"

echo "Ejecutando análisis de horarios pico..."
./run-spark-job.sh horarios_pico.py
check_success "Análisis de horarios"

echo "Ejecutando análisis de crecimiento..."
./run-spark-job.sh crecimiento.py
check_success "Análisis de crecimiento"

# 9. Mostrar resumen
echo -e "\n${GREEN}=== PIPELINE COMPLETADO EXITOSAMENTE ===${NC}"
echo ""
echo "Servicios disponibles:"
echo "  - Spark Master: http://localhost:6060"
echo "  - Hive: jdbc:hive2://localhost:10000"
if [ "$INCLUDE_AIRFLOW" = true ]; then
    echo "  - Airflow: http://localhost:8081 (admin/admin)"
fi
echo "  - ElasticSearch: http://localhost:9200"
echo ""
echo "Tablas creadas en el Data Warehouse:"
echo "  - Dimensiones: dim_tiempo, dim_usuario, dim_restaurante, dim_menu"
echo "  - Hechos: hechos_reservas"
echo "  - Análisis: dw_tendencias_consumo, dw_horarios_pico, dw_crecimiento_mensual"
echo ""
echo "Próximos pasos:"
if [ "$INCLUDE_AIRFLOW" = true ]; then
    echo "  1. Acceder a Airflow y activar el DAG 'restaurantes_etl_pipeline'"
fi
echo "  2. Configurar dashboards en Metabase/Superset"
echo "  3. Implementar análisis con Neo4j"

