# ADR-003: Usar AWS Lambda en lugar de ECS

## Estado

Aceptado

## Contexto

El procesamiento de Bread Boss ocurre principalmente por eventos: pedido creado, stock actualizado, pedido enviado a cocina, pedido listo, delivery asignado y notificación enviada.

La carga no es constante durante todo el día. Existen picos fuertes, especialmente viernes por la noche, fines de semana y campañas promocionales.

Se necesita una solución que escale bajo demanda sin mantener servidores encendidos todo el tiempo.

## Decisión

Se decide utilizar AWS Lambda para implementar los consumidores principales de eventos.

Cada función Lambda se encarga de una responsabilidad específica:

- `ingress`
- `kitchen-manager`
- `stock-updater`
- `delivery-tracker`
- `notifier`
- `ai-ops-agent`

## Alternativas evaluadas

### Amazon ECS

ECS permite ejecutar contenedores con mayor control sobre runtime, dependencias y procesos largos. Sin embargo, para este caso implica más configuración operativa que Lambda.

### EC2 tradicional

Fue descartado porque requiere administración de servidores, escalado manual o políticas más complejas, y mayor costo en períodos de baja demanda.

## Consecuencias positivas

- Escala automáticamente ante picos.
- Pago por invocación.
- Menor administración de infraestructura.
- Buena integración con servicios AWS.
- Permite separar responsabilidades por función.

## Consecuencias negativas

- Tiene límites de timeout.
- Puede haber cold starts.
- Requiere cuidar conexiones con Kafka/MSK.
- No es ideal para procesos largos o altamente persistentes.