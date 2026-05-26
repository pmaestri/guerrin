import json
import boto3
import urllib.request
import os
from datetime import datetime, timedelta
from decimal import Decimal
from collections import Counter


# ── HANDLER PRINCIPAL ──────────────────────────────────────────────────────────

CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

def lambda_handler(event, context):
    # Soporte para invocación vía HTTP (Function URL) y directa (EventBridge/test)
    qs = event.get("queryStringParameters") or {}
    fecha = qs.get("fecha") or event.get("fecha") or datetime.now().strftime("%Y-%m-%d")

    # Preflight CORS
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    openai_key = os.environ.get("OPENAI_API_KEY")
    orders_table = os.environ.get("ORDERS_TABLE", "breadboss-orders")
    resumenes_table = os.environ.get("RESUMENES_TABLE", "breadboss_resumenes")
    metricas_table = os.environ.get("METRICAS_TABLE", "breadboss_metricas")
    umbral_min = int(os.environ.get("ENTREGA_UMBRAL_MIN", "45"))

    if not openai_key:
        return {"statusCode": 500, "headers": CORS_HEADERS, "body": "Falta OPENAI_API_KEY en variables de entorno"}

    dynamodb = boto3.resource("dynamodb")

    # Cache: si ya existe el reporte del día, devolverlo sin llamar a OpenAI
    reporte_existente = _get_reporte_guardado(dynamodb, resumenes_table, metricas_table, fecha)
    if reporte_existente:
        return {
            "statusCode": 200,
            "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
            "body": json.dumps(reporte_existente, ensure_ascii=False),
        }

    table = dynamodb.Table(orders_table)

    # Pedidos del día
    pedidos = _query_by_fecha(table, fecha)
    if not pedidos:
        return {"statusCode": 404, "headers": CORS_HEADERS, "body": f"No hay pedidos para la fecha {fecha}"}

    # Pedidos de la semana anterior (para tendencia)
    fecha_anterior = (datetime.strptime(fecha, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    pedidos_anterior = _query_by_fecha(table, fecha_anterior)

    metricas = _calcular_metricas(pedidos, pedidos_anterior, umbral_min, fecha_anterior)
    resumen_ai = _llamar_openai(openai_key, fecha, metricas)
    _guardar_resultados(dynamodb, resumenes_table, metricas_table, fecha, resumen_ai, metricas)

    return {
        "statusCode": 200,
        "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
        "body": json.dumps({
            "fecha": fecha,
            "resumen": resumen_ai,
            "metricas": _to_json_safe(metricas)
        }, ensure_ascii=False)
    }


# ── CACHE: leer reporte ya guardado ───────────────────────────────────────────

def _get_reporte_guardado(dynamodb, resumenes_table, metricas_table, fecha):
    try:
        r = dynamodb.Table(resumenes_table).get_item(Key={"fecha": fecha})
        m = dynamodb.Table(metricas_table).get_item(Key={"fecha": fecha})
        resumen = r.get("Item", {}).get("resumen")
        metricas = m.get("Item")
        if resumen and metricas:
            metricas.pop("fecha", None)
            metricas.pop("generado_en", None)
            return {
                "fecha":    fecha,
                "resumen":  resumen,
                "metricas": _to_json_safe(metricas),
            }
    except Exception:
        pass
    return None


# ── QUERY DYNAMODB ─────────────────────────────────────────────────────────────

def _query_by_fecha(table, fecha):
    response = table.query(
        IndexName="fecha-index",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("fecha").eq(fecha)
    )
    return response.get("Items", [])


# ── CÁLCULO DE MÉTRICAS ────────────────────────────────────────────────────────

def _calcular_metricas(pedidos, pedidos_anterior, umbral_min, fecha_anterior):
    total = len(pedidos)
    entregados = [p for p in pedidos if p.get("status") == "entregado"]
    cancelados  = [p for p in pedidos if p.get("status") == "cancelado"]
    con_incidencia = [p for p in pedidos if p.get("incidencia", "ninguna") != "ninguna"]

    return {
        "operacionales": _metricas_operacionales(pedidos, entregados, cancelados, con_incidencia, total),
        "financieras":   _metricas_financieras(pedidos, total),
        "calidad":       _metricas_calidad(entregados, cancelados, con_incidencia, total, umbral_min),
        "tendencia":     _metricas_tendencia(pedidos, pedidos_anterior, fecha_anterior),
    }


def _metricas_operacionales(pedidos, entregados, cancelados, con_incidencia, total):
    # Pedidos por hora
    pedidos_por_hora = {}
    for p in pedidos:
        ts = int(p.get("timestamp", 0))
        hora = datetime.utcfromtimestamp(ts / 1000).strftime("%H") if ts > 0 else "00"
        pedidos_por_hora[hora] = pedidos_por_hora.get(hora, 0) + 1

    # Pedidos por canal
    pedidos_por_canal = {}
    for p in pedidos:
        canal = p.get("channel", "desconocido")
        pedidos_por_canal[canal] = pedidos_por_canal.get(canal, 0) + 1

    # Tiempo promedio por canal
    tiempo_acum = {}
    tiempo_count = {}
    for p in entregados:
        canal = p.get("channel", "desconocido")
        t = float(p.get("tiempo_entrega_min", 0) or 0)
        if t > 0:
            tiempo_acum[canal]  = tiempo_acum.get(canal, 0) + t
            tiempo_count[canal] = tiempo_count.get(canal, 0) + 1
    tiempo_promedio_por_canal = {
        c: round(tiempo_acum[c] / tiempo_count[c], 1) for c in tiempo_acum
    }

    tiempos_globales = [float(p.get("tiempo_entrega_min", 0) or 0) for p in entregados if float(p.get("tiempo_entrega_min", 0) or 0) > 0]

    # Tasa cancelación por canal
    cancelados_por_canal = {}
    for p in cancelados:
        canal = p.get("channel", "desconocido")
        cancelados_por_canal[canal] = cancelados_por_canal.get(canal, 0) + 1
    tasa_cancelacion_por_canal = {
        c: round(cancelados_por_canal.get(c, 0) / pedidos_por_canal[c] * 100, 1)
        for c in pedidos_por_canal
    }

    # Top items
    item_counter = Counter()
    for p in pedidos:
        items = p.get("items", [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    nombre = item.get("name", "desconocido")
                    qty    = int(item.get("qty", 1))
                    item_counter[nombre] += qty
                else:
                    item_counter[str(item)] += 1
        elif isinstance(items, str) and items:
            item_counter[items] += 1

    hora_pico = max(pedidos_por_hora, key=pedidos_por_hora.get) if pedidos_por_hora else None

    return {
        "total_pedidos":             total,
        "entregados":                len(entregados),
        "cancelados":                len(cancelados),
        "tasa_cancelacion_pct":      round(len(cancelados) / total * 100, 1) if total else 0,
        "tasa_incidencias_pct":      round(len(con_incidencia) / total * 100, 1) if total else 0,
        "pedidos_por_hora":          dict(sorted(pedidos_por_hora.items())),
        "hora_pico":                 hora_pico,
        "pedidos_por_canal":         pedidos_por_canal,
        "tiempo_promedio_global_min": round(sum(tiempos_globales) / len(tiempos_globales), 1) if tiempos_globales else 0,
        "tiempo_max_min":            max(tiempos_globales) if tiempos_globales else 0,
        "tiempo_promedio_por_canal": tiempo_promedio_por_canal,
        "tasa_cancelacion_por_canal": tasa_cancelacion_por_canal,
        "top_items":                 [{"item": k, "cantidad": v} for k, v in item_counter.most_common(5)],
    }


def _metricas_financieras(pedidos, total):
    revenue_por_canal = {}
    revenue_total = 0
    for p in pedidos:
        t = float(p.get("total", 0) or 0)
        canal = p.get("channel", "desconocido")
        revenue_total += t
        revenue_por_canal[canal] = revenue_por_canal.get(canal, 0) + t

    return {
        "revenue_total":     round(revenue_total, 2),
        "revenue_por_canal": {c: round(v, 2) for c, v in revenue_por_canal.items()},
        "ticket_promedio":   round(revenue_total / total, 2) if total else 0,
    }


def _metricas_calidad(entregados, cancelados, con_incidencia, total, umbral_min):
    # % a tiempo
    a_tiempo = [p for p in entregados if float(p.get("tiempo_entrega_min", 0) or 0) > 0
                and float(p.get("tiempo_entrega_min", 0)) <= umbral_min]
    pct_a_tiempo = round(len(a_tiempo) / len(entregados) * 100, 1) if entregados else 0

    # Reclamos
    reclamos = [p for p in con_incidencia if any(
        kw in p.get("incidencia", "").lower()
        for kw in ["reclam", "quej", "cliente reclamó"]
    )]

    # Causas de cancelación agrupadas
    causas = Counter()
    for p in cancelados:
        inc = p.get("incidencia", "desconocida").lower()
        if "stock" in inc:
            causas["sin stock"] += 1
        elif "cliente" in inc and ("cancel" in inc or "no atend" in inc):
            causas["cancelado por cliente"] += 1
        elif any(kw in inc for kw in ["técni", "tecni", "pago", "falla"]):
            causas["falla técnica"] += 1
        elif "demora" in inc:
            causas["demora"] += 1
        else:
            causas[p.get("incidencia", "desconocida")] += 1

    return {
        "pct_entregados_a_tiempo": pct_a_tiempo,
        "umbral_minutos":          umbral_min,
        "pedidos_con_reclamo":     len(reclamos),
        "causas_cancelacion":      dict(causas),
    }


def _metricas_tendencia(pedidos, pedidos_anterior, fecha_anterior):
    if not pedidos_anterior:
        return {"disponible": False}

    total_hoy      = len(pedidos)
    total_anterior = len(pedidos_anterior)
    rev_hoy        = sum(float(p.get("total", 0) or 0) for p in pedidos)
    rev_anterior   = sum(float(p.get("total", 0) or 0) for p in pedidos_anterior)

    entregados_hoy      = [p for p in pedidos         if p.get("status") == "entregado"]
    entregados_anterior = [p for p in pedidos_anterior if p.get("status") == "entregado"]
    cancelados_hoy      = [p for p in pedidos         if p.get("status") == "cancelado"]
    cancelados_anterior = [p for p in pedidos_anterior if p.get("status") == "cancelado"]

    def delta(a, b):
        return round((a - b) / b * 100, 1) if b else 0

    return {
        "disponible":           True,
        "fecha_anterior":       fecha_anterior,
        "pedidos_delta_pct":    delta(total_hoy, total_anterior),
        "revenue_delta_pct":    delta(rev_hoy, rev_anterior),
        "cancelados_delta_pct": delta(len(cancelados_hoy), len(cancelados_anterior)),
        "entregados_delta_pct": delta(len(entregados_hoy), len(entregados_anterior)),
        "total_anterior":       total_anterior,
        "revenue_anterior":     round(rev_anterior, 2),
    }


# ── LLAMADA A OPENAI ───────────────────────────────────────────────────────────

def _llamar_openai(openai_key, fecha, metricas):
    op  = metricas["operacionales"]
    fin = metricas["financieras"]
    cal = metricas["calidad"]
    tend = metricas["tendencia"]

    tend_txt = (
        f"Pedidos: {tend['pedidos_delta_pct']:+.1f}% | "
        f"Revenue: {tend['revenue_delta_pct']:+.1f}% | "
        f"Cancelados: {tend['cancelados_delta_pct']:+.1f}% "
        f"(vs {tend['fecha_anterior']})"
    ) if tend.get("disponible") else "Sin datos históricos disponibles"

    contexto = f"""
RESUMEN DEL DÍA — BreadBoss {fecha}

OPERACIONALES:
- Total pedidos: {op['total_pedidos']} | Entregados: {op['entregados']} | Cancelados: {op['cancelados']}
- Tasa cancelación global: {op['tasa_cancelacion_pct']}% | Tasa incidencias: {op['tasa_incidencias_pct']}%
- Tiempo promedio entrega: {op['tiempo_promedio_global_min']} min (máx: {op['tiempo_max_min']} min)
- Hora pico: {op['hora_pico']}hs con {op['pedidos_por_hora'].get(op['hora_pico'], 0)} pedidos
- Pedidos por canal: {json.dumps(op['pedidos_por_canal'])}
- Tiempo promedio por canal (min): {json.dumps(op['tiempo_promedio_por_canal'])}
- Tasa cancelación por canal (%): {json.dumps(op['tasa_cancelacion_por_canal'])}
- Top 5 items: {', '.join([f"{x['item']} x{x['cantidad']}" for x in op['top_items']])}

FINANCIERO:
- Revenue total: ${fin['revenue_total']:,.2f} | Ticket promedio: ${fin['ticket_promedio']:,.2f}
- Revenue por canal: {json.dumps(fin['revenue_por_canal'])}

CALIDAD:
- % entregados a tiempo (<{cal['umbral_minutos']} min): {cal['pct_entregados_a_tiempo']}%
- Pedidos con reclamo del cliente: {cal['pedidos_con_reclamo']}
- Causas de cancelación: {json.dumps(cal['causas_cancelacion'])}

TENDENCIA vs semana anterior:
{tend_txt}
"""

    system_prompt = (
        "Sos el analista de operaciones de BreadBoss, una dark kitchen multi-canal. "
        "Tu tarea es generar un resumen ejecutivo diario claro y accionable para C-Level. "
        "Usá tono profesional y directo. Incluí siempre:\n"
        "1. Estado general del día (1 párrafo)\n"
        "2. Puntos críticos o alertas (si los hay)\n"
        "3. 3 recomendaciones concretas para el día siguiente\n"
        "Respondé en español. Máximo 400 palabras."
    )

    payload = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": contexto}
        ],
        "max_tokens": 800,
        "temperature": 0.4
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {openai_key}"
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as res:
        resultado = json.loads(res.read().decode("utf-8"))

    return resultado["choices"][0]["message"]["content"]


# ── GUARDAR EN DYNAMODB ────────────────────────────────────────────────────────

def _guardar_resultados(dynamodb, resumenes_table, metricas_table, fecha, resumen_ai, metricas):
    generado_en = datetime.utcnow().isoformat() + "Z"

    dynamodb.Table(resumenes_table).put_item(Item={
        "fecha":        fecha,
        "resumen":      resumen_ai,
        "generado_en":  generado_en,
    })

    dynamodb.Table(metricas_table).put_item(Item=_to_decimal({
        "fecha":        fecha,
        "generado_en":  generado_en,
        **metricas,
    }))


# ── UTILIDADES ─────────────────────────────────────────────────────────────────

def _to_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_decimal(i) for i in obj]
    return obj


def _to_json_safe(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_safe(i) for i in obj]
    return obj
