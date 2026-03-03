#!/bin/bash

# Script simplificado para iniciar el proyecto OLAP

echo "=== INICIANDO PROYECTO OLAP - RESTAURANTES ==="
echo ""

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 1. Verificar driver JDBC
echo -e "${BLUE}1. Verificando driver JDBC...${NC}"
if [ ! -f "drivers/postgresql-42.5.1.jar" ]; then
    echo "Descargando driver..."
    mkdir -p drivers
    wget -q https://jdbc.postgresql.org/download/postgresql-42.5.1.jar -P drivers/
    echo -e "${GREEN}Driver descargado${NC}"
else
    echo -e "${GREEN}Driver ya existe${NC}"
fi

# 2. Copiar CSVs si no están
echo -e "\n${BLUE}2. Verificando archivos CSV...${NC}"
if [ ! -f "spark/data/usuarios.csv" ]; then
    echo "Copiando CSVs desde ../data/"
    mkdir -p spark/data
    cp ../data/*.csv spark/data/ 2>/dev/null || echo -e "${YELLOW}No se encontraron CSVs en ../data/${NC}"
fi
ls spark/data/*.csv 2>/dev/null | wc -l | xargs -I {} echo "Archivos CSV encontrados: {}"

# 3. Dar permisos
echo -e "\n${BLUE}3. Configurando permisos...${NC}"
chmod +x run-spark-job.sh 2>/dev/null
chmod +x hive/entrypoint.sh 2>/dev/null
echo -e "${GREEN}Permisos configurados${NC}"

# 4. Limpiar contenedores anteriores
echo -e "\n${BLUE}4. Limpiando contenedores anteriores...${NC}"
docker-compose -f docker-compose-simple.yml down 2>/dev/null
docker-compose -f docker-compose-airflow.yml down 2>/dev/null
echo -e "${GREEN}Limpieza completada${NC}"

# 5. Levantar servicios básicos (sin Airflow por ahora)
echo -e "\n${BLUE}5. Levantando servicios del Data Warehouse...${NC}"
echo "Usando configuración sin Airflow para empezar más rápido"
docker-compose -f docker-compose-simple.yml up -d

# 6. Esperar servicios
echo -e "\n${BLUE}6. Esperando a que los servicios estén listos...${NC}"
echo "Esto puede tomar 1-2 minutos..."

# Esperar PostgreSQL
echo -n "PostgreSQL"
for i in {1..30}; do
    if docker exec postgres-metastore pg_isready -U hive &>/dev/null; then
        echo -e " ${GREEN}OK${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

# Esperar Hive
echo -n "Hive"
for i in {1..60}; do
    if docker logs hive 2>&1 | grep -q "Hive está listo"; then
        echo -e " ${GREEN}OK${NC}"
        break
    fi
    echo -n "."
    sleep 3
done

# Esperar un poco más para asegurar que todo esté listo
sleep 10

# 7. Ejecutar ETL
echo -e "\n${BLUE}7. Cargando datos al Data Warehouse...${NC}"
./run-spark-job.sh etl_from_csv.py

# 8. Verificar carga
echo -e "\n${BLUE}8. Verificando datos cargados...${NC}"
docker exec hive beeline -u jdbc:hive2://localhost:10000 --silent=true -e "
USE restaurantes_dw;
SELECT 'Tablas creadas:' as info;
SHOW TABLES;
SELECT '';
SELECT 'Total registros en hechos_reservas:' as info, COUNT(*) as total FROM hechos_reservas;
" 2>/dev/null | grep -v "^$" | grep -v "SLF4J"

# 9. Preguntar si ejecutar análisis
echo -e "\n${YELLOW}¿Deseas ejecutar los análisis con Spark? (s/n)${NC}"
read -p "> " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Ss]$ ]]; then
    echo -e "\n${BLUE}Ejecutando análisis...${NC}"
    
    echo "1. Tendencias de consumo..."
    ./run-spark-job.sh tendencias.py
    
    echo -e "\n2. Horarios pico..."
    ./run-spark-job.sh horarios_pico.py
    
    echo -e "\n3. Crecimiento mensual..."
    ./run-spark-job.sh crecimiento.py
fi

# 10. Resumen final
echo -e "\n${GREEN}=== PROYECTO INICIADO EXITOSAMENTE ===${NC}"
echo ""
echo "URLs de acceso:"
echo "  - Spark UI: http://localhost:6060"
echo "  - ElasticSearch: http://localhost:9200"
echo ""
echo "Para conectar a Hive:"
echo "  docker exec -it hive beeline -u jdbc:hive2://localhost:10000"
echo ""
echo "Para ver las tablas de análisis:"
echo "  USE restaurantes_dw;"
echo "  SELECT * FROM dw_tendencias_consumo LIMIT 10;"
echo "  SELECT * FROM dw_horarios_pico LIMIT 10;"
echo "  SELECT * FROM dw_crecimiento_mensual LIMIT 10;"
echo ""
echo "Para levantar Airflow más tarde:"
echo "  docker-compose -f docker-compose-airflow.yml up -d"

