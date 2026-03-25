"""
routers/db_explorer.py
-----------------------
Endpoint REST per esplorare il database dal frontend.
Solo operazioni di lettura (SELECT) — nessuna modifica consentita.

Endpoints:
  GET  /db/tables              → lista di tutte le tabelle
  GET  /db/tables/{table}      → schema della tabella (colonne + tipi)
  GET  /db/tables/{table}/data → prime N righe della tabella
  POST /db/query               → esegue una query SELECT custom
"""

import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db

router = APIRouter(prefix="/db", tags=["db-explorer"])

# ── Sicurezza: whitelist SQL statement ────────────────────────────

_FORBIDDEN_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|EXEC|EXECUTE|"
    r"CALL|COPY|VACUUM|ANALYZE|EXPLAIN\s+ANALYZE)\b",
    re.IGNORECASE,
)


def _validate_select_only(sql: str):
    """
    Rifiuta qualsiasi query che non sia un SELECT puro.
    Raises HTTPException 400 se la query contiene istruzioni non permesse.
    """
    stripped = sql.strip()
    if not re.match(r"^\s*(SELECT|WITH)\b", stripped, re.IGNORECASE):
        raise HTTPException(
            400,
            "Solo query SELECT e WITH…SELECT sono permesse nel DB Explorer."
        )
    if _FORBIDDEN_PATTERN.search(stripped):
        raise HTTPException(
            400,
            "La query contiene istruzioni non permesse (INSERT, UPDATE, DELETE, DROP, ecc.)."
        )


# ── Request models ────────────────────────────────────────────────

class QueryRequest(BaseModel):
    sql: str
    limit: int = 100   # max righe restituite


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/tables")
def list_tables(db: Session = Depends(get_db)):
    """Lista tutte le tabelle presenti nel database."""
    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    result = []
    for table in sorted(tables):
        try:
            count_row = db.execute(
                text(f"SELECT COUNT(*) FROM {table}")
            ).scalar()
        except Exception:
            count_row = None
        result.append({"name": table, "row_count": count_row})
    return result


@router.get("/tables/{table_name}")
def get_table_schema(table_name: str, db: Session = Depends(get_db)):
    """
    Ritorna lo schema (colonne, tipi, nullable, default, primary key)
    di una tabella specifica.
    """
    inspector = inspect(db.bind)
    tables = inspector.get_table_names()

    if table_name not in tables:
        raise HTTPException(404, f"Tabella '{table_name}' non trovata")

    columns = inspector.get_columns(table_name)
    pk_cols  = {c for c in inspector.get_pk_constraint(table_name).get("constrained_columns", [])}
    indexes  = inspector.get_indexes(table_name)

    return {
        "table":   table_name,
        "columns": [
            {
                "name":       c["name"],
                "type":       str(c["type"]),
                "nullable":   c.get("nullable", True),
                "default":    str(c.get("default", "")) if c.get("default") is not None else None,
                "primary_key": c["name"] in pk_cols,
            }
            for c in columns
        ],
        "indexes": [
            {
                "name":    idx.get("name"),
                "columns": idx.get("column_names", []),
                "unique":  idx.get("unique", False),
            }
            for idx in indexes
        ],
    }


@router.get("/tables/{table_name}/data")
def get_table_data(
    table_name: str,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    Ritorna le prime N righe di una tabella con paginazione.
    Max limit: 500.
    """
    limit = min(limit, 500)

    inspector = inspect(db.bind)
    if table_name not in inspector.get_table_names():
        raise HTTPException(404, f"Tabella '{table_name}' non trovata")

    try:
        rows = db.execute(
            text(f"SELECT * FROM {table_name} LIMIT :limit OFFSET :offset"),
            {"limit": limit, "offset": offset},
        ).mappings().all()

        total = db.execute(
            text(f"SELECT COUNT(*) FROM {table_name}")
        ).scalar()

        return {
            "table":  table_name,
            "total":  total,
            "offset": offset,
            "limit":  limit,
            "rows":   [dict(r) for r in rows],
        }
    except SQLAlchemyError as e:
        raise HTTPException(500, f"Errore database: {e}")


@router.post("/query")
def execute_query(req: QueryRequest, db: Session = Depends(get_db)):
    """
    Esegue una query SELECT custom.
    Solo SELECT e WITH…SELECT sono permessi.
    Il risultato è limitato a req.limit righe (max 500).
    """
    limit = min(req.limit, 500)
    _validate_select_only(req.sql)

    # Wrappa la query per forzare il limite di sicurezza
    safe_sql = f"SELECT * FROM ({req.sql.rstrip(';')}) AS _q LIMIT :limit"

    try:
        rows = db.execute(text(safe_sql), {"limit": limit}).mappings().all()
        # Conta righe senza il limite (per mostrare "X di Y risultati")
        count_sql = f"SELECT COUNT(*) FROM ({req.sql.rstrip(';')}) AS _q"
        try:
            total = db.execute(text(count_sql)).scalar()
        except Exception:
            total = len(rows)

        return {
            "total":   total,
            "showing": len(rows),
            "columns": list(rows[0].keys()) if rows else [],
            "rows":    [dict(r) for r in rows],
        }
    except SQLAlchemyError as e:
        raise HTTPException(400, f"Errore SQL: {e}")