LOAD CSV WITH HEADERS FROM 'file:///osm_street_names.csv' AS row
CALL {
  WITH row
  WITH row.node_id AS id, row.street_name AS name
  MATCH (c:Calle) WHERE c.id = id
  SET c.nombre = name
} IN TRANSACTIONS OF 500 ROWS; 