"""Модуль для работы с базой данных Firebird"""
import logging
from typing import Optional, Dict, Any
import fdb
from config import DB_CONFIG

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Класс для управления подключением к базе данных Firebird"""

    def __init__(self):
        self.connection = None

    def connect(self):
        """Устанавливает подключение к базе данных"""
        try:
            if self.connection is None or self.connection.closed:
                self.connection = fdb.connect(
                    host=DB_CONFIG["host"],
                    port=DB_CONFIG["port"],
                    database=DB_CONFIG["database"],
                    user=DB_CONFIG["user"],
                    password=DB_CONFIG["password"],
                    charset=DB_CONFIG["charset"]
                )
                logger.info("Успешное подключение к базе данных Firebird")
            return self.connection
        except Exception as e:
            logger.error(f"Ошибка подключения к базе данных: {str(e)}")
            raise

    def disconnect(self):
        """Закрывает подключение к базе данных"""
        if self.connection and not self.connection.closed:
            self.connection.close()
            logger.info("Подключение к базе данных закрыто")


# Глобальный экземпляр подключения
db = DatabaseConnection()


def get_order_data(order_code: str) -> Optional[Dict[str, Any]]:
    """
    Получает данные заказа из базы данных по уникальному коду

    Args:
        order_code: Уникальный код заказа для поиска (поле Unique_code)

    Returns:
        Словарь с данными заказа или None если не найдено
    """
    try:
        connection = db.connect()

        # SQL запрос для получения данных заказа по Unique_code
        query = """
        SELECT
            o.id,
            o.orderno,
            o.totalprice,
            SUM(CASE WHEN uf.fieldname = 'qty_izd' THEN ouf.var_flt ELSE NULL END) as qty_izd,
            SUM(CASE WHEN uf.fieldname = 'area_izd' THEN ouf.var_flt ELSE NULL END) as area_izd,
            LIST(CASE WHEN uf.fieldname = 'delivery_zone' THEN ouf.var_str ELSE NULL END) as zone,
            LIST(CASE WHEN uf.fieldname = 'measurer' THEN ouf.var_str ELSE NULL END) as measurer,
            o.adressinstall,
            o.agreementdate,
            o.agreementno,
            o.phoneinstall
        FROM orders o
        JOIN orders_uf_values ouf ON ouf.orderid = o.id
        JOIN userfields uf ON uf.userfieldid = ouf.userfieldid
        WHERE o.id = (
            SELECT ouf2.orderid
            FROM orders_uf_values ouf2
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
            logger.warning(f"Заказ с кодом {order_code} не найден")
            return None

        # Преобразуем результат в словарь
        data = {
            "order_id": row[0],
            "order_number": row[1] if row[1] else "",
            "total_price": float(row[2]) if row[2] else 0.0,
            "qty_izd": float(row[3]) if row[3] else 0.0,
            "area_izd": float(row[4]) if row[4] else 0.0,
            "zone": row[5] if row[5] else "",
            "measurer": row[6] if row[6] else "",
            "address": row[7] if row[7] else "",
            "agreement_date": row[8].isoformat() if row[8] else None,
            "agreement_no": row[9] if row[9] else "",
            "phone": row[10] if row[10] else ""
        }

        logger.info(f"Получены данные для заказа с кодом {order_code}: {data['order_number']}")
        return data

    except Exception as e:
        logger.error(f"Ошибка получения данных из БД: {str(e)}")
        raise
    finally:
        if 'cursor' in locals():
            cursor.close()
