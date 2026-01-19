from __future__ import annotations

from typing import Optional, Dict, Any

import fdb
from loguru import logger

from config_exporter import settings


class AltawinDatabase:
    """Firebird connection for Altawin queries."""

    def __init__(self) -> None:
        self.connection: Optional[fdb.Connection] = None

    def connect(self) -> fdb.Connection:
        if self.connection is None or self.connection.closed:
            self.connection = fdb.connect(
                host=settings.altawin_db_host,
                port=settings.altawin_db_port,
                database=settings.altawin_db_name,
                user=settings.altawin_db_user,
                password=settings.altawin_db_password,
                charset=settings.altawin_db_charset,
            )
            logger.info("Altawin DB connection established")
        return self.connection

    def disconnect(self) -> None:
        if self.connection and not self.connection.closed:
            self.connection.close()
            logger.info("Altawin DB connection closed")


altawin_db = AltawinDatabase()


def get_order_data(order_code: str) -> Optional[Dict[str, Any]]:
    """
    Fetch order data from Altawin by Unique_code.

    Returns a dict with the same keys as Altawin API (order_number, qty_izd, area_izd, zone, etc.).
    """
    if not order_code:
        return None

    try:
        connection = altawin_db.connect()
        query = """
        SELECT
            o.id,
            o.orderno,
            o.totalprice,
            SUM(CASE WHEN uf.fieldname = 'qty_izd' THEN ouf.var_flt ELSE NULL END) AS qty_izd,
            SUM(CASE WHEN uf.fieldname = 'area_izd' THEN ouf.var_flt ELSE NULL END) AS area_izd,
            LIST(CASE WHEN uf.fieldname = 'delivery_zone' THEN ouf.var_str ELSE NULL END) AS zone,
            LIST(CASE WHEN uf.fieldname = 'measurer' THEN ouf.var_str ELSE NULL END) AS measurer,
            o.adressinstall,
            o.agreementdate,
            o.agreementno,
            o.phoneinstall
        FROM orders o
        JOIN order_uf_values ouf ON ouf.orderid = o.id
        JOIN userfields uf ON uf.userfieldid = ouf.userfieldid
        WHERE o.id = (
            SELECT ouf2.orderid
            FROM order_uf_values ouf2
            JOIN userfields uf2 ON uf2.userfieldid = ouf2.userfieldid
            WHERE uf2.fieldname = 'Unique_code'
                AND TRIM(ouf2.var_str) = ?
        )
        GROUP BY o.id, o.orderno, o.totalprice, o.adressinstall, o.agreementdate, o.agreementno, o.phoneinstall
        """

        cursor = connection.cursor()
        cursor.execute(query, (order_code.strip(),))
        row = cursor.fetchone()

        if not row:
            logger.warning(f"Altawin order not found for code: {order_code}")
            return None

        return {
            "order_id": row[0],
            "order_number": row[1] if row[1] else "",
            "total_price": float(row[2]) if row[2] is not None else None,
            "qty_izd": float(row[3]) if row[3] is not None else None,
            "area_izd": float(row[4]) if row[4] is not None else None,
            "zone": row[5] if row[5] else "",
            "measurer": row[6] if row[6] else "",
            "address": row[7] if row[7] else "",
            "agreement_date": row[8].isoformat() if row[8] else None,
            "agreement_no": row[9] if row[9] else "",
            "phone": row[10] if row[10] else "",
        }

    except Exception as exc:
        logger.error(f"Altawin DB query error for code {order_code}: {exc}")
        return None
    finally:
        try:
            cursor.close()
        except Exception:
            pass
