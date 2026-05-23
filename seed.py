"""
seed.py — Carga datos históricos de prueba en ghostbite-orders
Genera pedidos para los últimos 14 días (2026) con variación realista por día.

Uso:
    python3 seed.py
"""

import boto3
import random
from decimal import Decimal
from datetime import datetime, timedelta

# ── CONFIGURACIÓN ──────────────────────────────────────────────────────────────

TABLE_NAME = "ghostbite-orders"
REGION     = "us-east-1"
FECHA_FIN  = datetime(2026, 5, 22)   # hoy
DIAS       = 14                       # cuántos días hacia atrás generar

# ── CATÁLOGO DE ITEMS ──────────────────────────────────────────────────────────

MENU = [
    {"itemId": "b01", "name": "Hamburguesa Clasica",  "price": 4500},
    {"itemId": "b02", "name": "Hamburguesa BBQ",      "price": 5200},
    {"itemId": "b03", "name": "Hamburguesa Doble",    "price": 6800},
    {"itemId": "p01", "name": "Pizza Muzza",          "price": 6000},
    {"itemId": "p02", "name": "Pizza Napolitana",     "price": 6500},
    {"itemId": "p03", "name": "Pizza Especial",       "price": 7500},
    {"itemId": "e01", "name": "Empanadas x6",         "price": 4800},
    {"itemId": "c01", "name": "Combo Familiar",       "price": 12000},
    {"itemId": "c02", "name": "Combo Kids",           "price": 3500},
    {"itemId": "d01", "name": "Coca Cola",            "price": 1500},
    {"itemId": "d02", "name": "Agua Mineral",         "price": 800},
    {"itemId": "d03", "name": "Jugo Natural",         "price": 1200},
    {"itemId": "f01", "name": "Papas Grandes",        "price": 2500},
    {"itemId": "f02", "name": "Aros de Cebolla",      "price": 2200},
]

CANALES = ["app_mobile", "app_mobile", "app_mobile", "whatsapp", "rappi", "pedidosya", "web"]

INCIDENCIAS_ENTREGA = [
    "ninguna", "ninguna", "ninguna", "ninguna", "ninguna",
    "demora por trafico",
    "demora en cocina - cocina saturada",
    "cliente reclamo demora",
    "producto llegó frio",
    "ninguna",
]

INCIDENCIAS_CANCELACION = [
    "item sin stock",
    "cliente cancelo",
    "falla tecnica en pago",
    "demora excesiva - cliente no esperó",
    "direccion incorrecta",
]

# ── DISTRIBUCIÓN DE PEDIDOS POR HORA ──────────────────────────────────────────
# Simula pico al mediodía y a la noche

HORAS_PESO = {
    11: 2, 12: 5, 13: 6, 14: 4,   # almuerzo
    19: 3, 20: 8, 21: 9, 22: 6, 23: 3,  # cena
}


def hora_aleatoria():
    horas  = list(HORAS_PESO.keys())
    pesos  = list(HORAS_PESO.values())
    return random.choices(horas, weights=pesos, k=1)[0]


def generar_items():
    n_items = random.choices([1, 2, 3], weights=[50, 35, 15], k=1)[0]
    seleccion = random.sample(MENU, n_items)
    items = []
    for item in seleccion:
        qty = random.choices([1, 2], weights=[75, 25], k=1)[0]
        items.append({
            "itemId": item["itemId"],
            "name":   item["name"],
            "qty":    qty,
            "price":  item["price"],
        })
    return items


def calcular_total(items):
    return sum(i["price"] * i["qty"] for i in items)


def generar_pedido(fecha_str, fecha_dt, pedido_num, es_finde):
    """Genera un pedido con datos realistas."""
    channel = random.choice(CANALES)
    hora    = hora_aleatoria()
    minuto  = random.randint(0, 59)
    ts      = int(fecha_dt.replace(hour=hora, minute=minuto, second=0).timestamp() * 1000)

    # Más cancelaciones en fines de semana (mayor volumen, más saturación)
    prob_cancelacion = 0.22 if es_finde else 0.15
    cancelado = random.random() < prob_cancelacion

    items = generar_items()
    total = calcular_total(items)

    if cancelado:
        incidencia       = random.choice(INCIDENCIAS_CANCELACION)
        status           = "cancelado"
        tiempo_entrega   = 0
    else:
        incidencia       = random.choice(INCIDENCIAS_ENTREGA)
        status           = "entregado"
        # Rappi y web tienden a tardar más
        base = {"app_mobile": 25, "whatsapp": 30, "rappi": 45, "pedidosya": 35, "web": 40}.get(channel, 30)
        tiempo_entrega   = max(10, int(random.gauss(base, 10)))

    return {
        "orderId":           f"{fecha_str.replace('-','')}-{pedido_num:04d}",
        "timestamp":         ts,
        "fecha":             fecha_str,
        "channel":           channel,
        "status":            status,
        "incidencia":        incidencia,
        "tiempo_entrega_min": Decimal(str(tiempo_entrega)),
        "total":             Decimal(str(total)),
        "customerId":        f"user_{random.randint(1000, 9999)}",
        "items": [
            {k: (Decimal(str(v)) if isinstance(v, (int, float)) else v) for k, v in item.items()}
            for item in items
        ],
    }


# ── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    random.seed(42)  # reproducible
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table    = dynamodb.Table(TABLE_NAME)

    total_cargados = 0

    for d in range(DIAS - 1, -1, -1):  # del más viejo al más nuevo
        fecha_dt  = FECHA_FIN - timedelta(days=d)
        fecha_str = fecha_dt.strftime("%Y-%m-%d")
        es_finde  = fecha_dt.weekday() >= 5  # sábado o domingo

        # Más pedidos los fines de semana y crecimiento gradual
        crecimiento  = 1 + (DIAS - 1 - d) * 0.03  # +3% por día más reciente
        base_pedidos = 18 if es_finde else 12
        n_pedidos    = int(base_pedidos * crecimiento)

        print(f"\n📅 {fecha_str} {'(finde)' if es_finde else ''} — generando {n_pedidos} pedidos...")

        with table.batch_writer() as batch:
            for i in range(1, n_pedidos + 1):
                pedido = generar_pedido(fecha_str, fecha_dt, i, es_finde)
                batch.put_item(Item=pedido)
                total_cargados += 1

        entregados  = int(n_pedidos * (0.78 if es_finde else 0.85))
        cancelados  = n_pedidos - entregados
        print(f"   ✓ {n_pedidos} pedidos | ~{entregados} entregados | ~{cancelados} cancelados")

    print(f"\n{'='*50}")
    print(f"✅ Total cargados: {total_cargados} pedidos en {DIAS} días")
    print(f"   Tabla: {TABLE_NAME}")
    print(f"   Rango: {(FECHA_FIN - timedelta(days=DIAS-1)).strftime('%Y-%m-%d')} → {FECHA_FIN.strftime('%Y-%m-%d')}")
    print(f"\nPara auditar un día:")
    print(f"  aws lambda invoke --function-name breadboss-auditor \\")
    print(f"    --payload '{{\"fecha\":\"2026-05-22\"}}' \\")
    print(f"    --cli-binary-format raw-in-base64-out /tmp/out.json")


if __name__ == "__main__":
    main()
