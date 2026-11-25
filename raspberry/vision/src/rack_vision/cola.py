"""Cola local de mensajes pendientes (SQLite) para cuando no hay conexión con AWS IoT.

Si la Pi pierde la red, sigue clasificando y guarda cada mensaje aquí; al reconectar se reenvían en
orden. Sobrevive a reinicios del servicio. Se limita a MAX_PENDIENTES para no llenar la SD.
"""
import sqlite3
from pathlib import Path

MAX_PENDIENTES = 5000


class ColaPendientes:
    def __init__(self, ruta: str | Path):
        self.db = sqlite3.connect(str(ruta))
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS pendientes ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL)"
        )
        self.db.commit()

    def agregar(self, payload: str) -> None:
        self.db.execute("INSERT INTO pendientes (payload) VALUES (?)", (payload,))
        # Si se pasa del límite, se descartan los más viejos
        self.db.execute(
            "DELETE FROM pendientes WHERE id NOT IN "
            "(SELECT id FROM pendientes ORDER BY id DESC LIMIT ?)", (MAX_PENDIENTES,)
        )
        self.db.commit()

    def primeros(self, n: int) -> list[tuple[int, str]]:
        return self.db.execute(
            "SELECT id, payload FROM pendientes ORDER BY id LIMIT ?", (n,)
        ).fetchall()

    def borrar(self, id_: int) -> None:
        self.db.execute("DELETE FROM pendientes WHERE id = ?", (id_,))
        self.db.commit()

    def __len__(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM pendientes").fetchone()[0]
