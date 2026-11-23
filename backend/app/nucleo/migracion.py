"""Crea las tablas y pasa los pedidos de la version anterior (solo litofanos) al formato multiproducto."""
import json

from sqlalchemy import inspect, text
from sqlmodel import SQLModel

from .modelos import Pedido  # noqa: F401  (registra la tabla)

# columnas del litofano en la version anterior -> valor por defecto si la base era aun mas vieja
CONFIG_LITOFANO_V1 = {"forma": "panel", "material": "petg", "ancho": 150, "diametro": 80, "alto": 100,
                      "encuadre_x": 0.5, "encuadre_y": 0.5, "zoom": 1.0, "mejorar": True}


def iniciar(engine):
    with engine.begin() as con:
        tablas = inspect(con).get_table_names()
        viejas = "pedido" in tablas and "config" not in {c["name"] for c in inspect(con).get_columns("pedido")}
        if viejas:
            con.execute(text("ALTER TABLE pedido RENAME TO pedido_v1"))
    SQLModel.metadata.create_all(engine)
    if viejas:
        _migrar_v1(engine)
    with engine.begin() as con:
        if "archivos" not in {c["name"] for c in inspect(con).get_columns("pedido")}:
            con.execute(text("ALTER TABLE pedido ADD COLUMN archivos JSON NOT NULL DEFAULT '[]'"))


def _migrar_v1(engine):
    with engine.begin() as con:
        columnas = {c["name"] for c in inspect(con).get_columns("pedido_v1")}
        for fila in con.execute(text("SELECT * FROM pedido_v1")).mappings():
            config = {k: fila[k] if k in columnas and fila[k] is not None else v
                      for k, v in CONFIG_LITOFANO_V1.items()}
            config["mejorar"] = bool(config["mejorar"])
            resumen = {"gramos": fila["gramos"], "medidas": fila["medidas"]} if fila["stl_listo"] else {}
            con.execute(
                text("INSERT INTO pedido (id, linea, cliente, telefono, canal, producto, precio, anticipo, "
                     "estado, notas, fecha_entrega, creado, carpeta, archivo, config, generado, resumen) "
                     "VALUES (:id, 'litofano', :cliente, :telefono, :canal, :producto, :precio, :anticipo, "
                     ":estado, :notas, :fecha_entrega, :creado, :carpeta, :archivo, :config, :generado, :resumen)"),
                {**{k: fila[k] for k in ("id", "cliente", "telefono", "canal", "producto", "precio", "anticipo",
                                         "estado", "notas", "fecha_entrega", "creado", "carpeta")},
                 "archivo": fila["foto_nombre"], "config": json.dumps(config),
                 "generado": bool(fila["stl_listo"]), "resumen": json.dumps(resumen)})
        con.execute(text("DROP TABLE pedido_v1"))
