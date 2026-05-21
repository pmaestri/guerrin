# Bread Boss

## Arquitectura event-driven para una dark kitchen multi-canal en México

**Bread Boss** es una dark kitchen 100% digital ubicada en México, enfocada en la venta de productos gastronómicos por múltiples canales digitales. La operación no cuenta con salón físico ni atención tradicional en mesa: todo el negocio depende de recibir, procesar, preparar, despachar y notificar pedidos de forma rápida y confiable.

La empresa recibe pedidos desde distintos frentes de venta:

- App mobile propia.
- Web app.
- WhatsApp Bot.
- Marketplaces de delivery.

El desafío principal es que todos estos canales generan pedidos al mismo tiempo, especialmente en horarios pico, como viernes por la noche, fines de semana o campañas promocionales. Si la arquitectura no está preparada para absorber esa demanda, la operación puede perder pedidos, generar demoras, saturar cocina y aumentar reclamos de clientes.

---

## Problema de negocio

Bread Boss creció rápidamente incorporando nuevos canales digitales, pero su arquitectura inicial estaba pensada como un flujo centralizado y acoplado. Cada pedido dependía de que varios procesos respondieran en cadena: validación, stock, cocina, delivery y notificaciones.

Este enfoque genera cuatro problemas principales:

### 1. Canales acoplados al core

Cada vez que se quiere sumar un nuevo canal de venta, como un marketplace adicional o una integración con una campaña externa, es necesario modificar partes sensibles del sistema principal.

Esto aumenta el riesgo de regresiones, retrasa la salida de nuevas funcionalidades y limita la capacidad de crecimiento comercial.

### 2. Pedidos perdidos en hora pico

Durante momentos de alta demanda, el sistema puede recibir más pedidos de los que puede procesar de forma síncrona. Si cocina, stock o delivery se saturan, los pedidos pueden quedar demorados, procesarse fuera de orden o directamente perderse.

En un negocio gastronómico digital, cada pedido perdido representa facturación no capturada y posible pérdida de confianza del cliente.

### 3. Baja visibilidad post-compra

El cliente necesita saber en qué estado está su pedido: recibido, en preparación, listo, en camino o entregado. Cuando el sistema no actualiza estados en tiempo real, aumentan los reclamos, los llamados a soporte y la incertidumbre.

Esto impacta directamente en la experiencia del cliente.

### 4. Dificultad para escalar componentes específicos

No todos los módulos del sistema tienen la misma carga. En hora pico puede saturarse cocina, pero no necesariamente notificaciones o delivery. En una arquitectura monolítica o fuertemente acoplada, escalar una parte específica del sistema es difícil o costoso.

---

## Objetivo de la solución

El objetivo es diseñar una arquitectura de aplicaciones moderna, escalable y resiliente que permita a Bread Boss procesar pedidos desde múltiples canales digitales sin depender de un flujo rígido y centralizado.

La solución propuesta utiliza una arquitectura **event-driven** basada en eventos, donde cada pedido genera mensajes que son consumidos por distintos servicios de forma independiente.

Esto permite que el sistema:

- Procese pedidos en paralelo.
- Escale consumidores específicos según demanda.
- Mantenga trazabilidad completa del ciclo de vida del pedido.
- Reduzca el acoplamiento entre canales, cocina, stock, delivery y notificaciones.
- Mejore la resiliencia ante fallas parciales.
- Facilite la incorporación de nuevos canales de venta.

---

## ¿Por qué event-driven?

En Bread Boss, un pedido no es una acción única. Es una secuencia de eventos operativos:

1. El cliente realiza un pedido.
2. El sistema valida el canal y los datos.
3. Se verifica stock.
4. Cocina recibe la orden.
5. Se actualiza el estado del pedido.
6. Se asigna delivery.
7. Se notifica al cliente.
8. Se registra la entrega.

Cada una de estas acciones puede ser ejecutada por un servicio distinto. Por eso, una arquitectura basada en eventos permite que cada área del sistema trabaje de manera independiente, sin bloquear a las demás.

La idea central es:

> Un pedido genera un evento. Ese evento puede ser consumido por múltiples servicios en paralelo.

---

## Arquitectura propuesta

La arquitectura se apoya en servicios administrados y serverless de AWS, usando Kafka como bus principal de eventos.

### Canales de entrada

- App Mobile
- Web App
- WhatsApp Bot
- Marketplaces de delivery

### Ingreso

- Amazon API Gateway
- AWS Lambda Ingress
- Amazon Cognito para autenticación

### Bus de eventos

- Amazon MSK con Kafka

### Consumers principales

- Kitchen Manager
- Stock Updater
- Delivery Tracker
- Notifier
- Analytics Consumer
- AI Operations Agent

### Persistencia y soporte

- Amazon DynamoDB
- Amazon ElastiCache Redis
- Amazon S3
- Amazon SNS / SES
- Amazon CloudWatch
- AWS X-Ray

---

## Flujo general del pedido

1. El cliente realiza un pedido desde alguno de los canales digitales.
2. API Gateway recibe la solicitud.
3. Lambda Ingress valida el pedido y publica un evento en Kafka.
4. Kafka distribuye el evento a diferentes consumidores.
5. Kitchen Manager envía el pedido a cocina.
6. Stock Updater actualiza disponibilidad de productos.
7. Delivery Tracker gestiona el estado de envío.
8. Notifier informa al cliente sobre el avance del pedido.
9. Analytics Consumer registra métricas operativas.
10. AI Operations Agent analiza eventos y recomienda acciones operativas.

---

## Topics principales de Kafka

Los eventos se organizan en distintos topics según el tipo de proceso:

- `pedidos`
- `cocina`
- `stock`
- `delivery`
- `notificaciones`
- `analytics`
- `risk-alerts`

Esta separación permite que cada servicio consuma únicamente los eventos que necesita.

---

## ¿Por qué no un monolito?

Un monolito puede ser una buena opción en etapas iniciales, pero para Bread Boss presenta limitaciones importantes.

El problema no es que el monolito esté mal construido, sino que el negocio cambió: ahora existen más canales, más demanda, más picos operativos y mayor necesidad de visibilidad en tiempo real.

### Limitaciones del monolito

- Un error en un módulo puede impactar en todo el sistema.
- Agregar nuevos canales requiere modificar el core.
- Escalar una parte específica del sistema es complejo.
- La trazabilidad del pedido queda distribuida en logs difíciles de interpretar.
- El procesamiento síncrono no acompaña bien los picos de demanda.

### Ventajas de event-driven

- Cada servicio procesa eventos de forma independiente.
- Si un consumer falla, los demás pueden seguir funcionando.
- Kafka permite retener mensajes y reprocesarlos.
- Se puede escalar solo el componente saturado.
- Es más simple agregar nuevos canales o consumidores.
- Se mejora la trazabilidad punta a punta.

---

## Decisiones de arquitectura

### Amazon MSK con Kafka

Se utiliza Kafka como bus de eventos porque permite fan-out nativo, múltiples consumidores independientes y reprocesamiento de mensajes.

### AWS Lambda

Se utilizan funciones serverless para procesar eventos bajo demanda, reduciendo infraestructura fija y permitiendo escalar automáticamente.

### DynamoDB

Se utiliza como base principal para pedidos y estados operativos por su baja latencia y escalabilidad.

### Redis / ElastiCache

Se utiliza para estados temporales y consultas rápidas, especialmente en tracking y estado actual del pedido.

### SNS / SES

Se utilizan para enviar notificaciones push, emails transaccionales y alertas operativas.

### CloudWatch + X-Ray

Se utilizan para observabilidad, métricas, trazabilidad distribuida y diagnóstico de errores.

---

## IA como parte de la solución

La solución incorpora un componente de inteligencia artificial agéntica mediante un LLM comercial vía API.

Este componente no reemplaza el procesamiento transaccional del pedido. Funciona como un **AI Operations Agent**, es decir, un copiloto operativo que analiza eventos, métricas y estados del sistema para recomendar acciones.

### Funciones del AI Operations Agent

- Analizar saturación de cocina.
- Detectar acumulación de pedidos.
- Identificar posibles cuellos de botella.
- Resumir el estado operativo.
- Recomendar acciones a supervisores.
- Generar alertas cuando el riesgo operativo es alto.

### Ejemplo de recomendación

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