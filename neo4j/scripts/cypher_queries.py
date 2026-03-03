#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Consultas Cypher para análisis de grafos y rutas en el sistema de restaurantes
"""

from __future__ import annotations
import logging
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)


class CypherQueries:
    def __init__(self,
                 uri: str = "bolt://localhost:7687",
                 user: str = "neo4j",
                 password: str = "restaurantes123"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    # --------------------------- Helpers ----------------------------
    def close(self):
        if self.driver:
            self.driver.close()

    def _section(self, title: str):
        print(f"\n{title}\n" + "-"*len(title))

    # ------------------ 1. Productos co-comprados -------------------
    def get_top_5_products_bought_together(self):
        # Primero intentamos con relaciones detalladas INCLUYE_DETALLE
        q_detailed = """
        MATCH (p1:Producto)<-[:INCLUYE_DETALLE]-(pe:Pedido)-[:INCLUYE_DETALLE]->(p2:Producto)
        WHERE p1.id < p2.id
        WITH p1, p2, COUNT(*) AS veces
        ORDER BY veces DESC
        LIMIT 5
        RETURN p1.titulo AS prod1,
               p2.titulo AS prod2,
               veces
        """
        
        # Fallback a relaciones simples INCLUYE si no hay INCLUYE_DETALLE
        q_simple = """
        MATCH (p1:Producto)<-[:INCLUYE]-(pe:Pedido)-[:INCLUYE]->(p2:Producto)
        WHERE p1.id < p2.id
        WITH p1, p2, COUNT(*) AS veces
        ORDER BY veces DESC
        LIMIT 5
        RETURN p1.titulo AS prod1,
               p2.titulo AS prod2,
               veces
        """
        
        with self.driver.session() as s:
            # Intentar primero con relaciones detalladas
            result = [r.data() for r in s.run(q_detailed)]
            if not result:
                # Si no hay resultados, usar relaciones simples
                log.info("No se encontraron relaciones INCLUYE_DETALLE, usando INCLUYE")
                result = [r.data() for r in s.run(q_simple)]
            return result

    # ------------------ 1.1. Co-compras por categoría ---------------
    def get_category_cobuying_patterns(self):
        q = """
        MATCH (p1:Producto)<-[:INCLUYE_DETALLE]-(pe:Pedido)-[:INCLUYE_DETALLE]->(p2:Producto)
        WHERE p1.categoria <> p2.categoria
        WITH p1.categoria as cat1, p2.categoria as cat2, count(*) as combinaciones
        WHERE combinaciones >= 5
        RETURN cat1, cat2, combinaciones
        ORDER BY combinaciones DESC
        LIMIT 5
        """
        with self.driver.session() as s:
            return [r.data() for r in s.run(q)]

    # ------------------ 1.2. Estadísticas de co-compras -------------
    def get_cobuying_statistics(self):
        q = """
        MATCH ()-[r:INCLUYE_DETALLE]->()
        WITH count(r) as total_detalle
        MATCH (pe:Pedido)-[:INCLUYE_DETALLE]->()
        WITH total_detalle, count(DISTINCT pe) as pedidos_con_detalle
        MATCH (pe:Pedido)
        WITH total_detalle, pedidos_con_detalle, count(pe) as total_pedidos
        RETURN total_detalle,
               pedidos_con_detalle,
               total_pedidos,
               round(toFloat(total_detalle) / pedidos_con_detalle, 2) as promedio_productos_por_pedido
        """
        with self.driver.session() as s:
            result = s.run(q).single()
            return result.data() if result else {}

    # ------------------ 2. Usuarios influyentes --------------------
    def get_influential_users(self):
        create = """
        CALL gds.graph.project(
          'usuarios-pedidos',
          ['Usuario','Pedido'],
          {REALIZO:{orientation:'UNDIRECTED'}}
        )"""
        pr = """
        CALL gds.pageRank.stream('usuarios-pedidos',
              {maxIterations:20,dampingFactor:0.85})
        YIELD nodeId, score
        WITH gds.util.asNode(nodeId) AS u, score
        WHERE u:Usuario
        RETURN u.email AS email,
               u.rol   AS rol,
               score
        ORDER BY score DESC
        LIMIT 10
        """
        fallback = """
        MATCH (u:Usuario)
        OPTIONAL MATCH (u)-[:REALIZO]->(p:Pedido)
        WITH u, COUNT(p) AS actividad
        WHERE actividad>0
        RETURN u.email AS email, u.rol AS rol, actividad
        ORDER BY actividad DESC
        LIMIT 10
        """
        with self.driver.session() as s:
            try:
                s.run(create)
                data = [r.data() for r in s.run(pr)]
                s.run("CALL gds.graph.drop('usuarios-pedidos', false)")
                return data
            except Exception as exc:
                log.warning("GDS no disponible (%s). Fallback por actividad.", exc)
                return [r.data() for r in s.run(fallback)]

    # ------------------ 3. Restaurantes populares ------------------
    def get_restaurants_by_category_and_rating(self, categoria: str | None = None, limit: int = 10):
        q = """
        MATCH (r:Restaurante)
        OPTIONAL MATCH (r)<-[:EN_RESTAURANTE]-(pe:Pedido)
        WHERE $cat IS NULL OR r.categoria = $cat
        WITH r, COUNT(pe) AS total
        RETURN r.nombre AS nombre,
               r.categoria AS categoria,
               total
        ORDER BY total DESC
        LIMIT $lim
        """
        with self.driver.session() as s:
            return [r.data() for r in s.run(q, cat=categoria, lim=limit)]

    # ------------------ 4. Estadísticas globales -------------------
    def get_graph_statistics(self):
        q = """
        MATCH (u:Usuario)        WITH COUNT(u) AS usuarios
        MATCH (r:Restaurante)    WITH usuarios, COUNT(r) AS restaurantes
        MATCH (p:Producto)       WITH usuarios, restaurantes, COUNT(p) AS productos
        MATCH (o:Pedido)         WITH usuarios, restaurantes, productos, COUNT(o) AS pedidos
        MATCH (c:Calle)          WITH usuarios, restaurantes, productos, pedidos, COUNT(c) AS calles
        MATCH ()-[rel]->()       RETURN usuarios, restaurantes, productos, pedidos,
                                        calles, COUNT(rel) AS total_relaciones
        """
        with self.driver.session() as s:
            return s.run(q).single().data()

    # ------------------ 5. Análisis de Recomendaciones -------------
    def get_top_recommenders(self, limit: int = 10):
        """Obtener usuarios que más recomendaciones han hecho"""
        q = """
        MATCH (u:Usuario)-[r:RECOMIENDA]->()
        WITH u, count(r) as total_recomendaciones, 
             collect(r.canal) as canales_usados
        RETURN u.email as email,
               u.rol as rol,
               total_recomendaciones,
               canales_usados
        ORDER BY total_recomendaciones DESC
        LIMIT $limit
        """
        with self.driver.session() as s:
            return [r.data() for r in s.run(q, limit=limit)]

    def get_most_recommended_users(self, limit: int = 10):
        """Obtener usuarios que más han sido recomendados"""
        q = """
        MATCH ()-[r:RECOMIENDA]->(u:Usuario)
        WITH u, count(r) as veces_recomendado,
             collect(r.canal) as canales_recibidos
        RETURN u.email as email,
               u.rol as rol,
               veces_recomendado,
               canales_recibidos
        ORDER BY veces_recomendado DESC
        LIMIT $limit
        """
        with self.driver.session() as s:
            return [r.data() for r in s.run(q, limit=limit)]

    def get_recommendation_network_stats(self):
        """Estadísticas de la red de recomendaciones"""
        q = """
        MATCH ()-[r:RECOMIENDA]->()
        WITH count(r) as total_recomendaciones,
             collect(r.canal) as todos_canales
        UNWIND todos_canales as canal
        WITH total_recomendaciones, canal, count(*) as uso_canal
        WITH total_recomendaciones, 
             collect({canal: canal, cantidad: uso_canal}) as distribucion_canales
        MATCH (u:Usuario)-[:RECOMIENDA]->()
        WITH total_recomendaciones, distribucion_canales, 
             count(DISTINCT u) as usuarios_que_recomiendan
        MATCH ()-[:RECOMIENDA]->(u:Usuario)
        WITH total_recomendaciones, distribucion_canales, usuarios_que_recomiendan,
             count(DISTINCT u) as usuarios_recomendados
        RETURN total_recomendaciones,
               usuarios_que_recomiendan,
               usuarios_recomendados,
               distribucion_canales
        """
        with self.driver.session() as s:
            result = s.run(q).single()
            return result.data() if result else {}

    def get_top_influencers_by_similarity(self, limit: int = 10):
        """Obtener usuarios más influyentes basado en relaciones INFLUYE_EN"""
        q = """
        MATCH (u:Usuario)-[r:INFLUYE_EN]->()
        WITH u, count(r) as total_influencias,
             avg(r.score) as score_promedio,
             sum(r.productos_comunes) as productos_comunes_total
        RETURN u.email as email,
               u.rol as rol,
               total_influencias,
               round(score_promedio, 4) as score_promedio,
               productos_comunes_total
        ORDER BY total_influencias DESC, score_promedio DESC
        LIMIT $limit
        """
        with self.driver.session() as s:
            return [r.data() for r in s.run(q, limit=limit)]

    def get_most_influenced_users(self, limit: int = 10):
        """Obtener usuarios que más han sido influenciados"""
        q = """
        MATCH ()-[r:INFLUYE_EN]->(u:Usuario)
        WITH u, count(r) as veces_influenciado,
             avg(r.score) as score_promedio_recibido
        RETURN u.email as email,
               u.rol as rol,
               veces_influenciado,
               round(score_promedio_recibido, 4) as score_promedio_recibido
        ORDER BY veces_influenciado DESC, score_promedio_recibido DESC
        LIMIT $limit
        """
        with self.driver.session() as s:
            return [r.data() for r in s.run(q, limit=limit)]

    def get_influence_network_stats(self):
        """Estadísticas de la red de influencia"""
        q = """
        MATCH ()-[r:INFLUYE_EN]->()
        WITH count(r) as total_influencias,
             min(r.score) as score_min,
             max(r.score) as score_max,
             avg(r.score) as score_promedio,
             avg(r.productos_comunes) as productos_comunes_promedio
        MATCH (u:Usuario)-[:INFLUYE_EN]->()
        WITH total_influencias, score_min, score_max, score_promedio, productos_comunes_promedio,
             count(DISTINCT u) as usuarios_influyentes
        MATCH ()-[:INFLUYE_EN]->(u:Usuario)
        WITH total_influencias, score_min, score_max, score_promedio, productos_comunes_promedio,
             usuarios_influyentes, count(DISTINCT u) as usuarios_influenciados
        RETURN total_influencias,
               usuarios_influyentes,
               usuarios_influenciados,
               round(score_min, 4) as score_min,
               round(score_max, 4) as score_max,
               round(score_promedio, 4) as score_promedio,
               round(productos_comunes_promedio, 2) as productos_comunes_promedio
        """
        with self.driver.session() as s:
            result = s.run(q).single()
            return result.data() if result else {}

    def find_recommendation_chains(self, max_length: int = 3):
        """Encontrar cadenas de recomendaciones (A recomienda B, B recomienda C, etc.)"""
        q = """
        MATCH path = (start:Usuario)-[:RECOMIENDA*1..$max_length]->(end:Usuario)
        WHERE start <> end
        WITH path, length(path) as chain_length
        ORDER BY chain_length DESC
        LIMIT 10
        RETURN [n in nodes(path) | n.email] as cadena_emails,
               chain_length,
               [r in relationships(path) | {canal: r.canal, fecha: r.fecha}] as detalles_relaciones
        """
        with self.driver.session() as s:
            return [r.data() for r in s.run(q, max_length=max_length)]

    def analyze_cross_influence_recommendations(self):
        """Analizar usuarios que tanto recomiendan como influyen"""
        q = """
        MATCH (u:Usuario)
        OPTIONAL MATCH (u)-[rec:RECOMIENDA]->()
        OPTIONAL MATCH (u)-[inf:INFLUYE_EN]->()
        WITH u, count(rec) as recomendaciones, count(inf) as influencias
        WHERE recomendaciones > 0 OR influencias > 0
        WITH u, recomendaciones, influencias,
             CASE 
                WHEN recomendaciones > 0 AND influencias > 0 THEN 'Ambos'
                WHEN recomendaciones > 0 THEN 'Solo Recomienda'
                WHEN influencias > 0 THEN 'Solo Influye'
                ELSE 'Ninguno'
             END as tipo_usuario
        RETURN u.email as email,
               u.rol as rol,
               recomendaciones,
               influencias,
               tipo_usuario
        ORDER BY recomendaciones DESC, influencias DESC
        LIMIT 15
        """
        with self.driver.session() as s:
            return [r.data() for r in s.run(q)]

    # ------------------ CLI helper ---------------------------------
    def run_all(self):
        print("=== ANÁLISIS DE GRAFOS RESTAURANTES ===")

        self._section("TOP 5 PRODUCTOS MAS COMPRADOS JUNTOS")
        cocompras = self.get_top_5_products_bought_together()
        if cocompras:
            for i, r in enumerate(cocompras, 1):
                print(f"{i}. {r['prod1']} + {r['prod2']} ({r['veces']} veces)")
        else:
            print("No se encontraron datos de co-compras")
            print("Ejecuta: python setup_cocompras.py")

        # Mostrar estadísticas de co-compras si están disponibles
        stats = self.get_cobuying_statistics()
        if stats.get('total_detalle', 0) > 0:
            self._section("ESTADISTICAS DE CO-COMPRAS")
            print(f"Total relaciones detalle: {stats['total_detalle']}")
            print(f"Pedidos con detalle: {stats['pedidos_con_detalle']}")
            print(f"Promedio productos/pedido: {stats['promedio_productos_por_pedido']}")
            
            self._section("PATRONES DE CO-COMPRAS POR CATEGORIA")
            patterns = self.get_category_cobuying_patterns()
            if patterns:
                for i, p in enumerate(patterns, 1):
                    print(f"{i}. {p['cat1']} + {p['cat2']} ({p['combinaciones']} veces)")
            else:
                print("No hay suficientes co-compras entre categorías diferentes")

        self._section("USUARIOS MAS INFLUYENTES")
        for i, u in enumerate(self.get_influential_users(), 1):
            act = u.get("actividad", f"{u.get('score',0):.4f}")
            print(f"{i}. {u['email']} - {u['rol']} (score/act: {act})")

        self._section("RESTAURANTES MAS POPULARES")
        for i, r in enumerate(self.get_restaurants_by_category_and_rating(), 1):
            print(f"{i}. {r['nombre']} - {r['categoria']} ({r['total']} pedidos)")

        self._section("ESTADISTICAS DEL GRAFO")
        for k, v in self.get_graph_statistics().items():
            print(f"{k:>16}: {v}")

        # Análisis de recomendaciones (solo si existen)
        rec_stats = self.get_recommendation_network_stats()
        if rec_stats.get('total_recomendaciones', 0) > 0:
            self._section("ANALISIS DE RECOMENDACIONES")
            print(f"Total recomendaciones: {rec_stats['total_recomendaciones']}")
            print(f"Usuarios que recomiendan: {rec_stats['usuarios_que_recomiendan']}")
            print(f"Usuarios recomendados: {rec_stats['usuarios_recomendados']}")
            
            print("\nDistribucion por canales:")
            for canal_info in rec_stats.get('distribucion_canales', []):
                print(f"   {canal_info['canal']}: {canal_info['cantidad']}")
            
            self._section("TOP USUARIOS QUE MAS RECOMIENDAN")
            for i, user in enumerate(self.get_top_recommenders(5), 1):
                canales = ', '.join(set(user['canales_usados']))
                print(f"{i}. {user['email']} ({user['rol']}) - {user['total_recomendaciones']} recomendaciones")
                print(f"   Canales: {canales}")

        # Análisis de influencia (solo si existen)
        inf_stats = self.get_influence_network_stats()
        if inf_stats.get('total_influencias', 0) > 0:
            self._section("ANALISIS DE INFLUENCIA IMPLICITA")
            print(f"Total relaciones de influencia: {inf_stats['total_influencias']}")
            print(f"Usuarios influyentes: {inf_stats['usuarios_influyentes']}")
            print(f"Usuarios influenciados: {inf_stats['usuarios_influenciados']}")
            print(f"Score promedio: {inf_stats['score_promedio']} (rango: {inf_stats['score_min']} - {inf_stats['score_max']})")
            print(f"Productos comunes promedio: {inf_stats['productos_comunes_promedio']}")
            
            self._section("TOP USUARIOS MAS INFLUYENTES")
            for i, user in enumerate(self.get_top_influencers_by_similarity(5), 1):
                print(f"{i}. {user['email']} ({user['rol']}) - {user['total_influencias']} influencias")
                print(f"   Score promedio: {user['score_promedio']}, Productos comunes: {user['productos_comunes_total']}")

            # Análisis cruzado
            self._section("ANALISIS CRUZADO: RECOMENDACION vs INFLUENCIA")
            cross_analysis = self.analyze_cross_influence_recommendations()
            for user in cross_analysis[:8]:  # Top 8
                tipo = user['tipo_usuario']
                print(f"{user['email']} ({user['rol']}) - {tipo}")
                print(f"   Recomendaciones: {user['recomendaciones']}, Influencias: {user['influencias']}")

        # Mostrar cadenas de recomendación si existen
        if rec_stats.get('total_recomendaciones', 0) > 0:
            chains = self.find_recommendation_chains(3)
            if chains:
                self._section("CADENAS DE RECOMENDACION")
                for i, chain in enumerate(chains[:3], 1):  # Top 3 cadenas
                    emails = ' -> '.join(chain['cadena_emails'])
                    print(f"{i}. {emails} (longitud: {chain['chain_length']})")


if __name__ == "__main__":
    CypherQueries().run_all()
