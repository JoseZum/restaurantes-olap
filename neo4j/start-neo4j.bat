@echo off
echo Iniciando Neo4J para Analisis de Grafos y Rutas
echo =======================================================

REM Crear directorios necesarios
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "import" mkdir import
if not exist "conf" mkdir conf
if not exist "plugins" mkdir plugins

echo.
echo Iniciando Neo4J...
docker-compose -f docker-compose.neo4j.yml up -d neo4j

echo.
echo Esperando a que Neo4J este listo...
timeout /t 30 /nobreak

echo.
echo Inicializando datos en Neo4J...
docker-compose -f docker-compose.neo4j.yml --profile init up neo4j-init

echo.
echo Iniciando API de rutas...
cd rutas_api
docker build -t rutas-api .
docker run -d -p 8000:8000 --name rutas-api -e NEO4J_URI=bolt://localhost:7687 -e NEO4J_USER=neo4j -e NEO4J_PASSWORD=restaurantes123 rutas-api
cd ..

echo.
echo Proyecto iniciado exitosamente!
echo.
echo Servicios disponibles:
echo    Neo4J Browser: http://localhost:7474
echo    Usuario: neo4j, Contrasena: restaurantes123
echo.
echo    API de Rutas: http://localhost:8000
echo    Documentacion: http://localhost:8000/docs
echo.
echo Endpoint de ejemplo:
echo    http://localhost:8000/ruta-optima?cliente_id=123^&restaurante_id=456
echo.
echo Para ejecutar analisis Cypher:
echo    cd scripts ^&^& python cypher_queries.py
echo.
pause 