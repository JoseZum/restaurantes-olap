#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inicializa el grafo Neo4j con:
- Usuarios, Restaurantes, Productos, Pedidos, Reservas
- Red vial OpenStreetMap (nodos :Calle y relaciones :ROAD)
- Relaciones lógicas entre entidades + anclaje CERCA_DE
"""

from __future__ import annotations
import os, sys, time, math, logging
from pathlib import Path

import pandas as pd
from neo4j import GraphDatabase

# ---------- Config --------------------------------------------------
DATA_DIR  = Path(os.getenv("DATA_DIR",
                   Path(__file__).resolve().parents[2] / "spark" / "data"))
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER      = os.getenv("NEO4J_USER", "neo4j")
PASSWORD  = os.getenv("NEO4J_PASSWORD", "restaurantes123")
OSM_FILE  = Path(os.getenv("OSM_FILE",
                   Path(__file__).resolve().parents[2] / "map.osm"))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

# ---------- Clase principal ----------------------------------------
class Neo4jGraphInitializer:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(USER, PASSWORD))

    # ------------ Conexión & housekeeping --------------------------
    def close(self):               # noqa: D401
        """Cerrar driver"""
        if self.driver:
            self.driver.close()

    def clear_db(self):
        with self.driver.session() as s:
            log.info("Limpiando la base...")
            s.run("MATCH (n) DETACH DELETE n")
            for idx in (
                "idx_usuario_id", "idx_restaurante_id", "idx_producto_id",
                "idx_pedido_id", "idx_calle_id",
            ):
                try:
                    s.run(f"DROP INDEX {idx} IF EXISTS")
                except Exception:
                    pass
        log.info("Base limpia")

    def create_indexes(self):
        ix = (
            "CREATE INDEX idx_usuario_id       IF NOT EXISTS FOR (u:Usuario)      ON (u.id)",
            "CREATE INDEX idx_restaurante_id   IF NOT EXISTS FOR (r:Restaurante)  ON (r.id)",
            "CREATE INDEX idx_producto_id      IF NOT EXISTS FOR (p:Producto)     ON (p.id)",
            "CREATE INDEX idx_pedido_id        IF NOT EXISTS FOR (pe:Pedido)      ON (pe.id)",
            "CREATE INDEX idx_calle_id         IF NOT EXISTS FOR (c:Calle)        ON (c.id)",
            "CREATE INDEX idx_rest_loc         IF NOT EXISTS FOR (r:Restaurante)  ON (r.lat, r.lon)",
            "CREATE INDEX idx_calle_loc        IF NOT EXISTS FOR (c:Calle)        ON (c.lat, c.lon)",
        )
        with self.driver.session() as s:
            for q in ix:
                s.run(q)
        log.info("Indices listos")

    # ------------ Carga de CSV -------------------------------------
    def load_usuarios(self):
        df = pd.read_csv(DATA_DIR / "usuarios.csv")
        q = """
        UNWIND $rows AS r
        CREATE (:Usuario {
            id:          toInteger(r.id),
            email:       r.email,
            rol:         r.rol,
            fecha_alta:  datetime(replace(r.fecha_alta, ' ', 'T'))
        })
        """
        with self.driver.session() as s:
            s.run(q, rows=df.to_dict("records"))
        log.info("Usuarios cargados: %s", len(df))

    def load_restaurantes(self):
        df = pd.read_csv(DATA_DIR / "restaurantes.csv")
        q = """
        UNWIND $rows AS r
        CREATE (:Restaurante {
            id:        toInteger(r.id),
            nombre:    r.nombre,
            categoria: r.categoria_local,
            lat:       toFloat(r.lat),
            lon:       toFloat(r.lon)
        })
        """
        with self.driver.session() as s:
            s.run(q, rows=df.to_dict("records"))
        log.info("Restaurantes cargados: %s", len(df))

    def load_productos(self):
        df = pd.read_csv(DATA_DIR / "menus.csv")
        q = """
        UNWIND $rows AS r
        CREATE (:Producto {
            id:             toInteger(r.id),          // <-- id REAL
            titulo:         r.titulo,
            categoria:      r.categoria,
            activo:         r.activo = 't',
            restaurante_id: toInteger(r.restaurante_id)
        })
        """
        with self.driver.session() as s:
            s.run(q, rows=df.to_dict("records"))
        log.info("Productos cargados: %s", len(df))

    def load_pedidos(self):
        df = pd.read_csv(DATA_DIR / "pedidos.csv")
        q = """
        UNWIND $rows AS r
        CREATE (:Pedido {
            id:             toInteger(r.id),
            total:          toFloat(r.total),
            estado:         r.estado,
            fecha_creacion: datetime(replace(r.fecha_creacion,' ','T')),
            restaurante_id: toInteger(r.restaurante_id),
            usuario_id:     toInteger(r.usuario_id),
            menu_id:        toInteger(r.menu_id)
        })
        """
        with self.driver.session() as s:
            s.run(q, rows=df.to_dict("records"))
        log.info("Pedidos cargados: %s", len(df))

    def load_reservas_rels(self):
        f = DATA_DIR / "reservas.csv"
        if not f.exists():
            log.warning("reservas.csv no encontrado, se omite RESERVO")
            return
        df = pd.read_csv(f)
        q = """
        UNWIND $rows AS r
        MATCH (u:Usuario {id: toInteger(r.usuario_id)}),
              (rst:Restaurante {id: toInteger(r.restaurante_id)})
        CREATE (u)-[:RESERVO {
            fecha:     date(r.fecha),
            hora:      r.hora,
            invitados: toInteger(r.invitados),
            estado:    r.estado
        }]->(rst)
        """
        with self.driver.session() as s:
            s.run(q, rows=df.to_dict("records"))
        log.info("Relaciones RESERVO: %s", len(df))

    # ------------ Relaciones clave ---------------------------------
    def create_core_relationships(self):
        with self.driver.session() as s:
            log.info("Creando REALIZO...")
            s.run("""
            MATCH (u:Usuario),(pe:Pedido)
            WHERE u.id = pe.usuario_id
            MERGE (u)-[:REALIZO]->(pe)""")

            log.info("Creando EN_RESTAURANTE...")
            s.run("""
            MATCH (pe:Pedido),(r:Restaurante)
            WHERE pe.restaurante_id = r.id
            MERGE (pe)-[:EN_RESTAURANTE]->(r)""")

            log.info("Creando INCLUYE...")
            s.run("""
            MATCH (pe:Pedido),(p:Producto)
            WHERE pe.menu_id = p.id
            MERGE (pe)-[:INCLUYE]->(p)""")

    def load_pedido_detalle(self):
        """
        Carga el archivo pedido_detalle.csv y crea relaciones detalladas 
        (:Pedido)-[:INCLUYE {cantidad, precio}]->(:Producto) para análisis de co-compras.
        
        Este archivo es generado por generate_pedido_detalle.py y es independiente
        del pipeline original.
        """
        detalle_file = Path(__file__).resolve().parent.parent / "data" / "pedido_detalle.csv"
        
        if not detalle_file.exists():
            log.warning("pedido_detalle.csv no encontrado - se omiten relaciones detalladas INCLUYE")
            log.info("Ejecuta generate_pedido_detalle.py para generar este archivo")
            return
        
        df = pd.read_csv(detalle_file)
        log.info("Cargando pedido_detalle.csv: %s registros", len(df))
        
        # Crear relaciones detalladas INCLUYE con cantidad y precio
        q = """
        UNWIND $rows AS r
        MATCH (pe:Pedido {id: toInteger(r.pedido_id)}),
              (p:Producto {id: toInteger(r.producto_id)})
        MERGE (pe)-[:INCLUYE_DETALLE {
            cantidad: toInteger(r.cantidad),
            precio_unitario: toFloat(r.precio_unitario),
            subtotal: toFloat(r.cantidad) * toFloat(r.precio_unitario)
        }]->(p)
        """
        
        with self.driver.session() as s:
            # Procesar en lotes para mejor rendimiento
            batch_size = 1000
            for i in range(0, len(df), batch_size):
                batch = df.iloc[i:i+batch_size]
                s.run(q, rows=batch.to_dict("records"))
                log.info("Procesado lote %s/%s", i+batch_size, len(df))
        
        log.info("Relaciones INCLUYE_DETALLE creadas: %s", len(df))

    # ------------ OpenStreetMap ------------------------------------
    def load_osm(self):
        if not OSM_FILE.exists():
            log.warning("map.osm no encontrado - se saltara OSM")
            return
        from osm_processor import OSMProcessor
        proc  = OSMProcessor(str(OSM_FILE))
        nodes, ways = proc.process()

        log.info("Nodos de calle: %s  |  Ways: %s", len(nodes), len(ways))

        with self.driver.session() as s:
            # nodos
            chunk = list(nodes.items())
            for i in range(0, len(chunk), 10_000):
                part = chunk[i:i+10_000]
                q = """
                UNWIND $rows AS n
                CREATE (:Calle {id:n.id, lat:n.lat, lon:n.lon})
                """
                s.run(q, rows=[{"id":str(k), **v} for k, v in part])

            # relaciones ROAD
            for way in ways:
                pairs = zip(way["nodes"], way["nodes"][1:])
                rel_rows = []
                for a, b in pairs:
                    la, lo = nodes[a]["lat"], nodes[a]["lon"]
                    lb, lo2 = nodes[b]["lat"], nodes[b]["lon"]
                    dist = math.sqrt((la-lb)**2 + (lo-lo2)**2) * 111_000
                    rel_rows.append({"a": str(a), "b": str(b), "d": dist})
                q = """
                UNWIND $rows AS r
                MATCH (c1:Calle {id:r.a}),(c2:Calle {id:r.b})
                MERGE (c1)-[:ROAD {distancia:r.d}]->(c2)
                MERGE (c2)-[:ROAD {distancia:r.d}]->(c1)
                """
                s.run(q, rows=rel_rows)

    def anchor_restaurants(self):
        log.info("Conectando Restaurante -> Calle mas cercana...")
        with self.driver.session() as s:
            rst = s.run("MATCH (r:Restaurante) RETURN r.id AS id,r.lat AS lat,r.lon AS lon")
            for r in rst:
                calle = s.run("""
                MATCH (c:Calle)
                WITH c, abs(c.lat-$lat)+abs(c.lon-$lon) AS d
                ORDER BY d LIMIT 1
                RETURN c.id AS cid""",
                              lat=r["lat"], lon=r["lon"]).single()["cid"]
                s.run("""
                MATCH (r:Restaurante {id:$id}),(c:Calle {id:$cid})
                MERGE (r)-[:CERCA_DE {distancia:0}]->(c)""",
                      id=r["id"], cid=calle)

    # ------------ Orquestador --------------------------------------
    def run(self):
        try:
            self.clear_db()
            self.create_indexes()

            self.load_usuarios()
            self.load_restaurantes()
            self.load_productos()
            self.load_pedidos()
            self.load_reservas_rels()
            self.create_core_relationships()
            
            # Cargar detalles de pedido para análisis de co-compras
            self.load_pedido_detalle()

            self.load_osm()
            self.anchor_restaurants()
            log.info("Grafo inicializado con exito")
            return 0
        except Exception as e:
            log.exception("Error durante la inicialización: %s", e)
            return 1
        finally:
            self.close()


if __name__ == "__main__":
    sys.exit(Neo4jGraphInitializer().run())
