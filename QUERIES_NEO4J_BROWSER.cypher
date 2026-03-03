// ===============================================================================
// QUERIES DE CYPHER PARA NEO4J BROWSER - SISTEMA DE RUTAS OPTIMIZADAS
// ===============================================================================
// Copia y pega estas queries en Neo4j Browser (http://localhost:7474)
// Usuario: neo4j | Password: restaurantes123

// ===============================================================================
// 1. ESTADISTICAS GENERALES DEL SISTEMA
// ===============================================================================

// 1.1 Contar todos los nodos por tipo
MATCH (n)
RETURN labels(n) as TipoNodo, count(n) as Cantidad
ORDER BY Cantidad DESC;

// 1.2 Contar relaciones por tipo
MATCH ()-[r]->()
RETURN type(r) as TipoRelacion, count(r) as Cantidad
ORDER BY Cantidad DESC;

// 1.3 Estadísticas completas del grafo
MATCH (osm:OSMNode)
OPTIONAL MATCH (osm)-[r:OSM_ROAD]-()
WITH count(DISTINCT osm) as nodos_osm, count(r) as relaciones_osm
MATCH (rest:RestauranteOSM)
MATCH (client:ClienteOSM)
RETURN 
    nodos_osm as `Nodos OSM`,
    relaciones_osm as `Relaciones OSM_ROAD`,
    count(rest) as `Restaurantes`,
    count(client) as `Clientes`;

// ===============================================================================
// 2. CONSULTAR RESTAURANTES Y CLIENTES
// ===============================================================================

// 2.1 Ver todos los restaurantes
MATCH (r:RestauranteOSM)
RETURN r.id, r.nombre, r.lat, r.lon, r.osm_node_id
ORDER BY r.id;

// 2.2 Ver todos los clientes
MATCH (c:ClienteOSM)
RETURN c.id, c.nombre, c.lat, c.lon, c.osm_node_id
ORDER BY c.id;

// 2.3 Ver restaurantes con sus nodos OSM
MATCH (r:RestauranteOSM)
MATCH (osm:OSMNode {osm_id: r.osm_node_id})
RETURN r.nombre, r.lat, r.lon, osm.osm_id, osm.lat, osm.lon
ORDER BY r.id;

// ===============================================================================
// 3. RUTAS BASICAS - CAMINO MAS CORTO
// ===============================================================================

// 3.1 Ruta más corta: Restaurante Centro -> Cliente A
MATCH (rest:OSMNode {osm_id: 2753121419})  // Restaurante Centro
MATCH (client:OSMNode {osm_id: 1311433681}) // Cliente A
MATCH path = shortestPath((rest)-[:OSM_ROAD*1..100]-(client))
RETURN path, length(path) as segmentos;

// 3.2 Ruta más corta: Restaurante Sur -> Cliente B (la más corta del sistema)
MATCH (rest:OSMNode {osm_id: 450502937})   // Restaurante Sur
MATCH (client:OSMNode {osm_id: 472395245}) // Cliente B
MATCH path = shortestPath((rest)-[:OSM_ROAD*1..100]-(client))
RETURN path, length(path) as segmentos;

// 3.3 Ruta más corta: Restaurante Este -> Cliente B
MATCH (rest:OSMNode {osm_id: 452651210})   // Restaurante Este
MATCH (client:OSMNode {osm_id: 472395245}) // Cliente B
MATCH path = shortestPath((rest)-[:OSM_ROAD*1..100]-(client))
RETURN path, length(path) as segmentos;

// ===============================================================================
// 4. RUTAS CON DETALLES - NODOS Y CALLES
// ===============================================================================

// 4.1 Ruta detallada con nombres de calles
MATCH (rest:OSMNode {osm_id: 2753121419})  // Restaurante Centro
MATCH (client:OSMNode {osm_id: 1311433681}) // Cliente A
MATCH path = shortestPath((rest)-[:OSM_ROAD*1..100]-(client))
WITH path, nodes(path) as route_nodes, relationships(path) as route_roads
RETURN 
    length(path) as total_segmentos,
    [n in route_nodes | {osm_id: n.osm_id, lat: n.lat, lon: n.lon}] as nodos,
    [r in route_roads | {nombre: r.name, distancia: r.distance}] as calles;

// 4.2 Primeros 10 pasos de una ruta
MATCH (rest:OSMNode {osm_id: 450502937})   // Restaurante Sur
MATCH (client:OSMNode {osm_id: 472395245}) // Cliente B
MATCH path = shortestPath((rest)-[:OSM_ROAD*1..100]-(client))
WITH nodes(path) as route_nodes, relationships(path) as route_roads
UNWIND range(0, CASE WHEN length(route_nodes) > 10 THEN 9 ELSE length(route_nodes)-1 END) as i
RETURN 
    i+1 as paso,
    route_nodes[i].osm_id as nodo_id,
    route_nodes[i].lat as latitud,
    route_nodes[i].lon as longitud,
    CASE WHEN i < length(route_roads) THEN route_roads[i].name ELSE 'DESTINO' END as calle,
    CASE WHEN i < length(route_roads) THEN route_roads[i].distance ELSE 0 END as distancia_m
ORDER BY i;

// ===============================================================================
// 5. ANALISIS DE CONECTIVIDAD
// ===============================================================================

// 5.1 Verificar conectividad entre todos los restaurantes y clientes
MATCH (rest:RestauranteOSM)
MATCH (client:ClienteOSM)
MATCH (rest_node:OSMNode {osm_id: rest.osm_node_id})
MATCH (client_node:OSMNode {osm_id: client.osm_node_id})
OPTIONAL MATCH path = shortestPath((rest_node)-[:OSM_ROAD*1..100]-(client_node))
RETURN 
    rest.nombre as restaurante,
    client.nombre as cliente,
    CASE WHEN path IS NOT NULL THEN length(path) ELSE 0 END as segmentos,
    CASE WHEN path IS NOT NULL THEN 'CONECTADO' ELSE 'SIN RUTA' END as estado
ORDER BY rest.id, client.id;

// 5.2 Contar nodos conectados vs aislados
MATCH (n:OSMNode)
OPTIONAL MATCH (n)-[:OSM_ROAD]-()
WITH n, count(*) as conexiones
RETURN 
    CASE WHEN conexiones > 0 THEN 'CONECTADO' ELSE 'AISLADO' END as estado,
    count(n) as cantidad
ORDER BY estado;

// 5.3 Top 10 nodos con más conexiones (intersecciones principales)
MATCH (n:OSMNode)-[r:OSM_ROAD]-()
WITH n, count(r) as conexiones
RETURN n.osm_id, n.lat, n.lon, conexiones
ORDER BY conexiones DESC
LIMIT 10;

// ===============================================================================
// 6. ANALISIS DE DISTANCIAS
// ===============================================================================

// 6.1 Las 5 rutas más cortas del sistema
MATCH (rest:RestauranteOSM)
MATCH (client:ClienteOSM)
MATCH (rest_node:OSMNode {osm_id: rest.osm_node_id})
MATCH (client_node:OSMNode {osm_id: client.osm_node_id})
MATCH path = shortestPath((rest_node)-[:OSM_ROAD*1..100]-(client_node))
WITH rest.nombre as restaurante, client.nombre as cliente, length(path) as segmentos, path
RETURN restaurante, cliente, segmentos
ORDER BY segmentos ASC
LIMIT 5;

// 6.2 Las 5 rutas más largas del sistema
MATCH (rest:RestauranteOSM)
MATCH (client:ClienteOSM)
MATCH (rest_node:OSMNode {osm_id: rest.osm_node_id})
MATCH (client_node:OSMNode {osm_id: client.osm_node_id})
MATCH path = shortestPath((rest_node)-[:OSM_ROAD*1..100]-(client_node))
WITH rest.nombre as restaurante, client.nombre as cliente, length(path) as segmentos, path
RETURN restaurante, cliente, segmentos
ORDER BY segmentos DESC
LIMIT 5;

// 6.3 Distancia promedio por restaurante
MATCH (rest:RestauranteOSM)
MATCH (client:ClienteOSM)
MATCH (rest_node:OSMNode {osm_id: rest.osm_node_id})
MATCH (client_node:OSMNode {osm_id: client.osm_node_id})
MATCH path = shortestPath((rest_node)-[:OSM_ROAD*1..100]-(client_node))
WITH rest.nombre as restaurante, collect(length(path)) as distancias
RETURN 
    restaurante,
    round(reduce(sum = 0, d IN distancias | sum + d) * 1.0 / size(distancias), 2) as segmentos_promedio,
    min(distancias) as min_segmentos,
    max(distancias) as max_segmentos
ORDER BY segmentos_promedio;

// ===============================================================================
// 7. EXPLORAR CALLES Y NOMBRES
// ===============================================================================

// 7.1 Top 10 calles más utilizadas en rutas
MATCH ()-[r:OSM_ROAD]-()
WHERE r.name IS NOT NULL AND r.name <> ''
RETURN r.name as calle, count(*) as frecuencia
ORDER BY frecuencia DESC
LIMIT 10;

// 7.2 Calles con nombres únicos
MATCH ()-[r:OSM_ROAD]-()
WHERE r.name IS NOT NULL AND r.name <> ''
RETURN DISTINCT r.name as calle
ORDER BY calle
LIMIT 20;

// 7.3 Estadísticas de nombres de calles
MATCH ()-[r:OSM_ROAD]-()
WITH 
    count(r) as total_relaciones,
    count(CASE WHEN r.name IS NOT NULL AND r.name <> '' THEN 1 END) as con_nombre,
    count(CASE WHEN r.name IS NULL OR r.name = '' THEN 1 END) as sin_nombre
RETURN 
    total_relaciones,
    con_nombre,
    sin_nombre,
    round(con_nombre * 100.0 / total_relaciones, 2) as porcentaje_con_nombre;

// ===============================================================================
// 8. QUERIES ESPECIFICAS PARA TESTING
// ===============================================================================

// 8.1 Verificar que todos los restaurantes están en nodos conectados
MATCH (rest:RestauranteOSM)
MATCH (osm:OSMNode {osm_id: rest.osm_node_id})
OPTIONAL MATCH (osm)-[:OSM_ROAD]-()
WITH rest, osm, count(*) as conexiones
RETURN 
    rest.nombre,
    rest.osm_node_id,
    conexiones,
    CASE WHEN conexiones > 0 THEN 'CONECTADO' ELSE 'AISLADO' END as estado;

// 8.2 Verificar que todos los clientes están en nodos conectados
MATCH (client:ClienteOSM)
MATCH (osm:OSMNode {osm_id: client.osm_node_id})
OPTIONAL MATCH (osm)-[:OSM_ROAD]-()
WITH client, osm, count(*) as conexiones
RETURN
    client.nombre,
    client.osm_node_id,
    conexiones,
    CASE WHEN conexiones > 0 THEN 'CONECTADO' ELSE 'AISLADO' END as estado;

// 8.3 Test de conectividad completa (debe devolver 25 rutas)
MATCH (rest:RestauranteOSM)
MATCH (client:ClienteOSM)
MATCH (rest_node:OSMNode {osm_id: rest.osm_node_id})
MATCH (client_node:OSMNode {osm_id: client.osm_node_id})
OPTIONAL MATCH path = shortestPath((rest_node)-[:OSM_ROAD*1..100]-(client_node))
RETURN count(path) as rutas_exitosas, count(*) as rutas_totales;

// ===============================================================================
// 9. QUERIES AVANZADAS - ANALISIS GEOGRAFICO
// ===============================================================================

// 9.1 Restaurante más céntrico (con más rutas cortas)
MATCH (rest:RestauranteOSM)
MATCH (client:ClienteOSM)
MATCH (rest_node:OSMNode {osm_id: rest.osm_node_id})
MATCH (client_node:OSMNode {osm_id: client.osm_node_id})
MATCH path = shortestPath((rest_node)-[:OSM_ROAD*1..100]-(client_node))
WITH rest.nombre as restaurante, collect(length(path)) as rutas
RETURN 
    restaurante,
    round(reduce(sum = 0, r IN rutas | sum + r) * 1.0 / size(rutas), 2) as promedio_segmentos
ORDER BY promedio_segmentos ASC;

// 9.2 Cliente más accesible (con rutas más cortas desde todos los restaurantes)
MATCH (rest:RestauranteOSM)
MATCH (client:ClienteOSM)
MATCH (rest_node:OSMNode {osm_id: rest.osm_node_id})
MATCH (client_node:OSMNode {osm_id: client.osm_node_id})
MATCH path = shortestPath((rest_node)-[:OSM_ROAD*1..100]-(client_node))
WITH client.nombre as cliente, collect(length(path)) as rutas
RETURN 
    cliente,
    round(reduce(sum = 0, r IN rutas | sum + r) * 1.0 / size(rutas), 2) as promedio_segmentos
ORDER BY promedio_segmentos ASC;

// ===============================================================================
// INSTRUCCIONES DE USO:
// ===============================================================================
// 1. Abrir Neo4j Browser: http://localhost:7474
// 2. Conectar con: neo4j / restaurantes123
// 3. Copiar y pegar cualquier query de arriba
// 4. Presionar Ctrl+Enter para ejecutar
// 5. Ver resultados en formato tabla o grafo
// =============================================================================== 