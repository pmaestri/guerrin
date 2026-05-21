# ADR-001: Usar Amazon MSK con Kafka en lugar de SQS

## Estado

Aceptado

## Contexto

Bread Boss recibe pedidos desde múltiples canales: app mobile, web app, WhatsApp Bot y marketplaces de delivery.

Cada pedido no debe ser procesado por un único flujo rígido, sino que debe disparar distintas acciones en paralelo: registrar el pedido, actualizar stock, enviar la orden a cocina, coordinar delivery, notificar al cliente, generar métricas y alimentar el agente de IA operativa.

El sistema necesita soportar múltiples consumidores independientes sobre los mismos eventos, especialmente durante horarios pico.

## Decisión

Se decide utilizar Amazon MSK con Kafka como bus principal de eventos.

Kafka permite publicar un evento una sola vez y que múltiples consumidores lo procesen de forma independiente mediante consumer groups.

## Alternativas evaluadas

### Amazon SQS

SQS es una opción más simple para colas de mensajes, pero está más orientado a procesamiento punto a punto. Para lograr fan-out hacia múltiples consumidores sería necesario combinar SQS con SNS o crear múltiples colas.

### Comunicación REST directa

La comunicación REST entre servicios fue descartada porque genera mayor acoplamiento, dependencia síncrona entre componentes y mayor riesgo de caída en cascada.

## Consecuencias positivas

- Permite fan-out nativo.
- Los consumidores pueden evolucionar de forma independiente.
- Permite retención y reprocesamiento de eventos.
- Mejora la trazabilidad del ciclo completo del pedido.
- Soporta mejor picos de demanda.

## Consecuencias negativas

- Mayor complejidad operativa que SQS.
- Requiere configuración de red, permisos y conectividad con MSK.
- Puede tener mayor costo base que una cola simple.