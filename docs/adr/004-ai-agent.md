# ADR-004: Incorporar un AI Operations Agent con LLM comercial vía API

## Estado

Aceptado

## Contexto

Bread Boss necesita mejorar la toma de decisiones operativas durante horarios pico.

La arquitectura event-driven genera eventos y métricas en tiempo real, pero los supervisores necesitan interpretar rápidamente qué está ocurriendo: si la cocina se está saturando, si un canal está generando demasiada carga, si aumentan las demoras o si conviene priorizar ciertos pedidos.

El objetivo no es entrenar un modelo propio desde cero, sino integrar inteligencia comercial de forma rápida y útil dentro del flujo operativo.

## Decisión

Se decide incorporar un AI Operations Agent basado en un LLM comercial vía API.

Este agente funcionará como un consumidor adicional de la arquitectura. Analizará eventos recientes, métricas operativas y estados del sistema para generar diagnósticos y recomendaciones.

El agente no tomará decisiones críticas de forma autónoma. Su rol será asistir a supervisores y responsables operativos.

## Entradas del agente

- Eventos de pedidos.
- Estados de cocina.
- Estado de stock.
- Eventos de delivery.
- Métricas de CloudWatch.
- Estado actual en Redis.
- Historial operativo en DynamoDB.

## Salidas del agente

- Resumen operativo.
- Nivel de riesgo.
- Causa probable del problema.
- Recomendaciones accionables.
- Alertas para supervisores.

## Ejemplo de respuesta

```json
{
  "riskLevel": "ALTO",
  "summary": "La cocina presenta saturación por acumulación de pedidos desde marketplaces.",
  "recommendedActions": [
    "Pausar marketplaces durante 10 minutos",
    "Priorizar pedidos con SLA menor a 15 minutos",
    "Enviar notificación preventiva a clientes demorados"
  ],
  "businessImpact": "Reduce riesgo de cancelaciones y reclamos en soporte."
}