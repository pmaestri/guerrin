"""
seed.py — Carga datos de prueba en DynamoDB para GhostBite/BreadBoss.

Inserta:
  - 14 items en breadboss-menu (menú completo con stock)
  - 30 pedidos en breadboss-orders (estados variados, últimos 3 días)

Uso:
    python3 seed.py
"""

import boto3
from decimal import Decimal
from datetime import datetime, timedelta

REGION       = "us-east-1"
ORDERS_TABLE = "breadboss-orders"
MENU_TABLE   = "breadboss-menu"

# ── MENÚ COMPLETO ──────────────────────────────────────────────────────────────

MENU = [
    {"itemId": "b01", "name": "Smash Burger Clásica",    "category": "hamburguesas",    "price": Decimal("4500"),  "stock": Decimal("80")},
    {"itemId": "b02", "name": "Smash Burger BBQ",        "category": "hamburguesas",    "price": Decimal("5200"),  "stock": Decimal("60")},
    {"itemId": "b03", "name": "Smash Burger Doble",      "category": "hamburguesas",    "price": Decimal("6800"),  "stock": Decimal("40")},
    {"itemId": "b04", "name": "Crispy Chicken Burger",   "category": "hamburguesas",    "price": Decimal("5500"),  "stock": Decimal("50")},
    {"itemId": "p01", "name": "Pizza Muzza",             "category": "pizzas",          "price": Decimal("6000"),  "stock": Decimal("30")},
    {"itemId": "p02", "name": "Pizza Napolitana",        "category": "pizzas",          "price": Decimal("6500"),  "stock": Decimal("25")},
    {"itemId": "p03", "name": "Pizza Especial",          "category": "pizzas",          "price": Decimal("7500"),  "stock": Decimal("20")},
    {"itemId": "e01", "name": "Empanadas x6",            "category": "entradas",        "price": Decimal("4800"),  "stock": Decimal("45")},
    {"itemId": "c01", "name": "Combo Familiar",          "category": "combos",          "price": Decimal("12000"), "stock": Decimal("20")},
    {"itemId": "c02", "name": "Combo Kids",              "category": "combos",          "price": Decimal("3500"),  "stock": Decimal("30")},
    {"itemId": "f01", "name": "Papas Grandes",           "category": "acompañamientos", "price": Decimal("2500"),  "stock": Decimal("90")},
    {"itemId": "f02", "name": "Aros de Cebolla",         "category": "acompañamientos", "price": Decimal("2200"),  "stock": Decimal("70")},
    {"itemId": "d01", "name": "Coca Cola 500ml",         "category": "bebidas",         "price": Decimal("1500"),  "stock": Decimal("100")},
    {"itemId": "d02", "name": "Agua Mineral 500ml",      "category": "bebidas",         "price": Decimal("800"),   "stock": Decimal("100")},
]

# ── PEDIDOS DE PRUEBA ──────────────────────────────────────────────────────────
# 30 pedidos distribuidos en los últimos 3 días con estados variados

HOY = datetime(2026, 5, 23)

def ts(dias_atras, hora, minuto):
    dt = (HOY - timedelta(days=dias_atras)).replace(hour=hora, minute=minuto, second=0)
    return int(dt.timestamp() * 1000)

def fecha(dias_atras):
    return (HOY - timedelta(days=dias_atras)).strftime("%Y-%m-%d")

PEDIDOS = [
    # ── HOY (2026-05-23) ── 10 pedidos
    {
        "orderId": "20260523-0001", "timestamp": ts(0, 11, 32), "fecha": fecha(0),
        "channel": "app_mobile", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_1042", "tiempo_entrega_min": Decimal("28"), "total": Decimal("9000"),
        "items": [{"itemId": "b01", "name": "Smash Burger Clásica", "qty": Decimal("1"), "price": Decimal("4500")},
                  {"itemId": "f01", "name": "Papas Grandes",        "qty": Decimal("1"), "price": Decimal("2500")},
                  {"itemId": "d01", "name": "Coca Cola 500ml",      "qty": Decimal("1"), "price": Decimal("1500")}],
    },
    {
        "orderId": "20260523-0002", "timestamp": ts(0, 12, 5), "fecha": fecha(0),
        "channel": "rappi", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_2187", "tiempo_entrega_min": Decimal("42"), "total": Decimal("15000"),
        "items": [{"itemId": "c01", "name": "Combo Familiar",  "qty": Decimal("1"), "price": Decimal("12000")},
                  {"itemId": "d01", "name": "Coca Cola 500ml", "qty": Decimal("2"), "price": Decimal("1500")}],
    },
    {
        "orderId": "20260523-0003", "timestamp": ts(0, 12, 48), "fecha": fecha(0),
        "channel": "whatsapp", "status": "entregado", "incidencia": "demora por trafico",
        "customerId": "user_3301", "tiempo_entrega_min": Decimal("55"), "total": Decimal("13000"),
        "items": [{"itemId": "p01", "name": "Pizza Muzza",     "qty": Decimal("1"), "price": Decimal("6000")},
                  {"itemId": "p02", "name": "Pizza Napolitana","qty": Decimal("1"), "price": Decimal("6500")}],
    },
    {
        "orderId": "20260523-0004", "timestamp": ts(0, 13, 15), "fecha": fecha(0),
        "channel": "app_mobile", "status": "cancelado", "incidencia": "cliente cancelo",
        "customerId": "user_4420", "tiempo_entrega_min": Decimal("0"), "total": Decimal("5200"),
        "items": [{"itemId": "b02", "name": "Smash Burger BBQ", "qty": Decimal("1"), "price": Decimal("5200")}],
    },
    {
        "orderId": "20260523-0005", "timestamp": ts(0, 20, 3), "fecha": fecha(0),
        "channel": "pedidosya", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_5512", "tiempo_entrega_min": Decimal("35"), "total": Decimal("11300"),
        "items": [{"itemId": "b03", "name": "Smash Burger Doble",   "qty": Decimal("1"), "price": Decimal("6800")},
                  {"itemId": "b01", "name": "Smash Burger Clásica", "qty": Decimal("1"), "price": Decimal("4500")}],
    },
    {
        "orderId": "20260523-0006", "timestamp": ts(0, 20, 45), "fecha": fecha(0),
        "channel": "app_mobile", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_6634", "tiempo_entrega_min": Decimal("30"), "total": Decimal("9300"),
        "items": [{"itemId": "b04", "name": "Crispy Chicken Burger","qty": Decimal("1"), "price": Decimal("5500")},
                  {"itemId": "f02", "name": "Aros de Cebolla",      "qty": Decimal("1"), "price": Decimal("2200")}],
    },
    {
        "orderId": "20260523-0007", "timestamp": ts(0, 21, 10), "fecha": fecha(0),
        "channel": "rappi", "status": "entregado", "incidencia": "producto llegó frio",
        "customerId": "user_7745", "tiempo_entrega_min": Decimal("50"), "total": Decimal("7500"),
        "items": [{"itemId": "p03", "name": "Pizza Especial", "qty": Decimal("1"), "price": Decimal("7500")}],
    },
    {
        "orderId": "20260523-0008", "timestamp": ts(0, 21, 33), "fecha": fecha(0),
        "channel": "app_mobile", "status": "cancelado", "incidencia": "item sin stock",
        "customerId": "user_8856", "tiempo_entrega_min": Decimal("0"), "total": Decimal("4800"),
        "items": [{"itemId": "e01", "name": "Empanadas x6", "qty": Decimal("1"), "price": Decimal("4800")}],
    },
    {
        "orderId": "20260523-0009", "timestamp": ts(0, 22, 5), "fecha": fecha(0),
        "channel": "whatsapp", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_9967", "tiempo_entrega_min": Decimal("33"), "total": Decimal("16800"),
        "items": [{"itemId": "c01", "name": "Combo Familiar", "qty": Decimal("1"), "price": Decimal("12000")},
                  {"itemId": "e01", "name": "Empanadas x6",   "qty": Decimal("1"), "price": Decimal("4800")}],
    },
    {
        "orderId": "20260523-0010", "timestamp": ts(0, 22, 50), "fecha": fecha(0),
        "channel": "app_mobile", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_1078", "tiempo_entrega_min": Decimal("27"), "total": Decimal("8200"),
        "items": [{"itemId": "b02", "name": "Smash Burger BBQ","qty": Decimal("1"), "price": Decimal("5200")},
                  {"itemId": "f01", "name": "Papas Grandes",   "qty": Decimal("1"), "price": Decimal("2500")}],
    },

    # ── AYER (2026-05-22) ── 11 pedidos
    {
        "orderId": "20260522-0001", "timestamp": ts(1, 12, 10), "fecha": fecha(1),
        "channel": "app_mobile", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_2034", "tiempo_entrega_min": Decimal("25"), "total": Decimal("6000"),
        "items": [{"itemId": "b01", "name": "Smash Burger Clásica","qty": Decimal("1"), "price": Decimal("4500")},
                  {"itemId": "d01", "name": "Coca Cola 500ml",     "qty": Decimal("1"), "price": Decimal("1500")}],
    },
    {
        "orderId": "20260522-0002", "timestamp": ts(1, 12, 55), "fecha": fecha(1),
        "channel": "rappi", "status": "entregado", "incidencia": "demora en cocina - cocina saturada",
        "customerId": "user_3145", "tiempo_entrega_min": Decimal("60"), "total": Decimal("13500"),
        "items": [{"itemId": "p01", "name": "Pizza Muzza",    "qty": Decimal("1"), "price": Decimal("6000")},
                  {"itemId": "p03", "name": "Pizza Especial", "qty": Decimal("1"), "price": Decimal("7500")}],
    },
    {
        "orderId": "20260522-0003", "timestamp": ts(1, 13, 20), "fecha": fecha(1),
        "channel": "pedidosya", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_4256", "tiempo_entrega_min": Decimal("38"), "total": Decimal("3500"),
        "items": [{"itemId": "c02", "name": "Combo Kids", "qty": Decimal("1"), "price": Decimal("3500")}],
    },
    {
        "orderId": "20260522-0004", "timestamp": ts(1, 13, 47), "fecha": fecha(1),
        "channel": "app_mobile", "status": "cancelado", "incidencia": "falla tecnica en pago",
        "customerId": "user_5367", "tiempo_entrega_min": Decimal("0"), "total": Decimal("6800"),
        "items": [{"itemId": "b03", "name": "Smash Burger Doble", "qty": Decimal("1"), "price": Decimal("6800")}],
    },
    {
        "orderId": "20260522-0005", "timestamp": ts(1, 20, 15), "fecha": fecha(1),
        "channel": "app_mobile", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_6478", "tiempo_entrega_min": Decimal("29"), "total": Decimal("9500"),
        "items": [{"itemId": "b04", "name": "Crispy Chicken Burger","qty": Decimal("1"), "price": Decimal("5500")},
                  {"itemId": "f01", "name": "Papas Grandes",        "qty": Decimal("1"), "price": Decimal("2500")},
                  {"itemId": "d02", "name": "Agua Mineral 500ml",   "qty": Decimal("1"), "price": Decimal("800")}],
    },
    {
        "orderId": "20260522-0006", "timestamp": ts(1, 21, 0), "fecha": fecha(1),
        "channel": "whatsapp", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_7589", "tiempo_entrega_min": Decimal("32"), "total": Decimal("12000"),
        "items": [{"itemId": "c01", "name": "Combo Familiar", "qty": Decimal("1"), "price": Decimal("12000")}],
    },
    {
        "orderId": "20260522-0007", "timestamp": ts(1, 21, 30), "fecha": fecha(1),
        "channel": "rappi", "status": "entregado", "incidencia": "cliente reclamo demora",
        "customerId": "user_8690", "tiempo_entrega_min": Decimal("48"), "total": Decimal("10400"),
        "items": [{"itemId": "b02", "name": "Smash Burger BBQ", "qty": Decimal("2"), "price": Decimal("5200")}],
    },
    {
        "orderId": "20260522-0008", "timestamp": ts(1, 21, 58), "fecha": fecha(1),
        "channel": "app_mobile", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_9701", "tiempo_entrega_min": Decimal("26"), "total": Decimal("6500"),
        "items": [{"itemId": "p02", "name": "Pizza Napolitana", "qty": Decimal("1"), "price": Decimal("6500")}],
    },
    {
        "orderId": "20260522-0009", "timestamp": ts(1, 22, 15), "fecha": fecha(1),
        "channel": "app_mobile", "status": "cancelado", "incidencia": "demora excesiva - cliente no esperó",
        "customerId": "user_1012", "tiempo_entrega_min": Decimal("0"), "total": Decimal("6700"),
        "items": [{"itemId": "b01", "name": "Smash Burger Clásica","qty": Decimal("1"), "price": Decimal("4500")},
                  {"itemId": "f02", "name": "Aros de Cebolla",     "qty": Decimal("1"), "price": Decimal("2200")}],
    },
    {
        "orderId": "20260522-0010", "timestamp": ts(1, 22, 40), "fecha": fecha(1),
        "channel": "pedidosya", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_1123", "tiempo_entrega_min": Decimal("36"), "total": Decimal("13600"),
        "items": [{"itemId": "b03", "name": "Smash Burger Doble", "qty": Decimal("2"), "price": Decimal("6800")}],
    },
    {
        "orderId": "20260522-0011", "timestamp": ts(1, 23, 5), "fecha": fecha(1),
        "channel": "app_mobile", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_1234", "tiempo_entrega_min": Decimal("31"), "total": Decimal("4800"),
        "items": [{"itemId": "e01", "name": "Empanadas x6", "qty": Decimal("1"), "price": Decimal("4800")}],
    },

    # ── ANTEAYER (2026-05-21) ── 9 pedidos
    {
        "orderId": "20260521-0001", "timestamp": ts(2, 12, 0), "fecha": fecha(2),
        "channel": "app_mobile", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_2345", "tiempo_entrega_min": Decimal("24"), "total": Decimal("8000"),
        "items": [{"itemId": "b04", "name": "Crispy Chicken Burger","qty": Decimal("1"), "price": Decimal("5500")},
                  {"itemId": "f01", "name": "Papas Grandes",        "qty": Decimal("1"), "price": Decimal("2500")}],
    },
    {
        "orderId": "20260521-0002", "timestamp": ts(2, 13, 30), "fecha": fecha(2),
        "channel": "rappi", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_3456", "tiempo_entrega_min": Decimal("40"), "total": Decimal("13600"),
        "items": [{"itemId": "c01", "name": "Combo Familiar",    "qty": Decimal("1"), "price": Decimal("12000")},
                  {"itemId": "d02", "name": "Agua Mineral 500ml","qty": Decimal("2"), "price": Decimal("800")}],
    },
    {
        "orderId": "20260521-0003", "timestamp": ts(2, 13, 50), "fecha": fecha(2),
        "channel": "whatsapp", "status": "cancelado", "incidencia": "item sin stock",
        "customerId": "user_4567", "tiempo_entrega_min": Decimal("0"), "total": Decimal("7500"),
        "items": [{"itemId": "p03", "name": "Pizza Especial", "qty": Decimal("1"), "price": Decimal("7500")}],
    },
    {
        "orderId": "20260521-0004", "timestamp": ts(2, 20, 5), "fecha": fecha(2),
        "channel": "app_mobile", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_5678", "tiempo_entrega_min": Decimal("27"), "total": Decimal("5200"),
        "items": [{"itemId": "b02", "name": "Smash Burger BBQ", "qty": Decimal("1"), "price": Decimal("5200")}],
    },
    {
        "orderId": "20260521-0005", "timestamp": ts(2, 20, 45), "fecha": fecha(2),
        "channel": "pedidosya", "status": "entregado", "incidencia": "producto llegó frio",
        "customerId": "user_6789", "tiempo_entrega_min": Decimal("52"), "total": Decimal("10800"),
        "items": [{"itemId": "p01", "name": "Pizza Muzza",  "qty": Decimal("1"), "price": Decimal("6000")},
                  {"itemId": "e01", "name": "Empanadas x6", "qty": Decimal("1"), "price": Decimal("4800")}],
    },
    {
        "orderId": "20260521-0006", "timestamp": ts(2, 21, 20), "fecha": fecha(2),
        "channel": "app_mobile", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_7890", "tiempo_entrega_min": Decimal("23"), "total": Decimal("6700"),
        "items": [{"itemId": "b01", "name": "Smash Burger Clásica","qty": Decimal("1"), "price": Decimal("4500")},
                  {"itemId": "f02", "name": "Aros de Cebolla",     "qty": Decimal("1"), "price": Decimal("2200")}],
    },
    {
        "orderId": "20260521-0007", "timestamp": ts(2, 21, 55), "fecha": fecha(2),
        "channel": "rappi", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_8901", "tiempo_entrega_min": Decimal("44"), "total": Decimal("12000"),
        "items": [{"itemId": "c01", "name": "Combo Familiar", "qty": Decimal("1"), "price": Decimal("12000")}],
    },
    {
        "orderId": "20260521-0008", "timestamp": ts(2, 22, 30), "fecha": fecha(2),
        "channel": "app_mobile", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_9012", "tiempo_entrega_min": Decimal("29"), "total": Decimal("8300"),
        "items": [{"itemId": "b03", "name": "Smash Burger Doble","qty": Decimal("1"), "price": Decimal("6800")},
                  {"itemId": "d01", "name": "Coca Cola 500ml",   "qty": Decimal("1"), "price": Decimal("1500")}],
    },
    {
        "orderId": "20260521-0009", "timestamp": ts(2, 23, 0), "fecha": fecha(2),
        "channel": "whatsapp", "status": "entregado", "incidencia": "ninguna",
        "customerId": "user_1234", "tiempo_entrega_min": Decimal("34"), "total": Decimal("6500"),
        "items": [{"itemId": "p02", "name": "Pizza Napolitana", "qty": Decimal("1"), "price": Decimal("6500")}],
    },
]


def main():
    dynamodb = boto3.resource("dynamodb", region_name=REGION)

    # Cargar menú
    menu_table = dynamodb.Table(MENU_TABLE)
    print(f"🍔 Cargando {len(MENU)} items en {MENU_TABLE}...")
    with menu_table.batch_writer() as batch:
        for item in MENU:
            batch.put_item(Item=item)
    print(f"   ✅ Menú cargado")

    # Cargar pedidos
    orders_table = dynamodb.Table(ORDERS_TABLE)
    entregados = sum(1 for p in PEDIDOS if p["status"] == "entregado")
    cancelados = sum(1 for p in PEDIDOS if p["status"] == "cancelado")

    print(f"\n📦 Cargando {len(PEDIDOS)} pedidos en {ORDERS_TABLE}...")
    print(f"   Rango: {fecha(2)} → {fecha(0)}")
    print(f"   {entregados} entregados | {cancelados} cancelados")

    with orders_table.batch_writer() as batch:
        for pedido in PEDIDOS:
            batch.put_item(Item=pedido)
    print(f"   ✅ Pedidos cargados")

    print(f"\n{'='*50}")
    print(f"✅ Seed completo. Para auditar:")
    print(f"   aws lambda invoke --function-name breadboss-auditor \\")
    print(f"     --payload '{{\"fecha\":\"{fecha(0)}\"}}' \\")
    print(f"     --cli-binary-format raw-in-base64-out /tmp/out.json && cat /tmp/out.json")


if __name__ == "__main__":
    main()
