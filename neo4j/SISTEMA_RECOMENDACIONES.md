# Sistema de Recomendaciones Simplificado

## 📋 Descripción
Sistema simple de recomendaciones entre usuarios que crea relaciones aleatorias tipo RECOMIENDA en Neo4j.

## 🚀 Características
- **Recomendaciones aleatorias**: Crea relaciones RECOMIENDA entre usuarios de forma aleatoria
- **Recomendaciones mutuas**: Algunas relaciones son bidireccionales para mayor realismo
- **Fechas realistas**: Asigna fechas de los últimos 3 meses
- **Estadísticas**: Muestra métricas del sistema

## 📊 Estadísticas Actuales
- **Total de recomendaciones**: 3,240
- **Usuarios que recomiendan**: 2,670
- **Usuarios recomendados**: 2,658
- **Recomendaciones mutuas**: 2,615 pares

## 🔧 Archivos Principales

### `scripts/setup_recommendations.py`
Script principal que configura el sistema de recomendaciones:
- Limpia recomendaciones existentes
- Crea recomendaciones aleatorias
- Crea recomendaciones mutuas
- Muestra estadísticas

### `scripts/test_recommendations.py`
Script de pruebas que verifica el funcionamiento:
- Top usuarios que más recomiendan
- Usuarios más recomendados
- Ejemplos de recomendaciones mutuas
- Cadenas de recomendación (A→B→C)
- Recomendaciones específicas por usuario

## 🎯 Tipos de Relaciones

### RECOMIENDA
Relación principal entre usuarios con propiedades:
- `fecha`: Fecha de la recomendación
- `tipo`: "aleatoria" o "mutua"

## 📈 Consultas Útiles

### Ver usuarios que más recomiendan
```cypher
MATCH (u:Usuario)-[r:RECOMIENDA]->()
RETURN u.email as usuario, count(r) as total_recomendaciones
ORDER BY total_recomendaciones DESC
LIMIT 10
```

### Ver usuarios más recomendados
```cypher
MATCH ()-[r:RECOMIENDA]->(u:Usuario)
RETURN u.email as usuario, count(r) as veces_recomendado
ORDER BY veces_recomendado DESC
LIMIT 10
```

### Ver recomendaciones mutuas
```cypher
MATCH (u1:Usuario)-[:RECOMIENDA]->(u2:Usuario)-[:RECOMIENDA]->(u1)
RETURN u1.email as usuario1, u2.email as usuario2
LIMIT 10
```

### Cadenas de recomendación
```cypher
MATCH path = (u1:Usuario)-[:RECOMIENDA]->(u2:Usuario)-[:RECOMIENDA]->(u3:Usuario)
WHERE u1 <> u3
RETURN u1.email as inicio, u2.email as intermedio, u3.email as fin
LIMIT 10
```

## 🚀 Ejecución

### Configurar el sistema
```bash
cd restaurantes-olap/neo4j/scripts
python setup_recommendations.py
```

### Probar el sistema
```bash
python test_recommendations.py
```

## ✅ Resultados
El sistema crea exitosamente:
- Miles de recomendaciones aleatorias
- Relaciones mutuas bidireccionales
- Estadísticas detalladas
- Consultas de prueba funcionales

## 🎉 Estado: FUNCIONANDO ✅
Sistema simplificado de recomendaciones operativo y probado.