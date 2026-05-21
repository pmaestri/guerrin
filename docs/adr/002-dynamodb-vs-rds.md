# ADR-002: Usar DynamoDB en lugar de RDS

## Estado

Aceptado

## Contexto

Bread Boss necesita guardar pedidos, estados operativos, timestamps y datos de seguimiento en tiempo casi real.

El patrón principal de acceso no es analítico ni relacional complejo. La mayoría de las consultas son por identificador de pedido, estado, canal, fecha o cliente.

Durante horarios pico, el sistema puede recibir muchos pedidos en poco tiempo, por lo que se necesita una base de datos con baja latencia y capacidad de escalar sin administración manual de servidores.

## Decisión

Se decide utilizar Amazon DynamoDB como base principal para pedidos y estados operativos.

La tabla principal será `orders`, con `orderId` como clave primaria y atributos para estado, canal, timestamps, cliente, items, total y datos de delivery.

## Alternativas evaluadas

### Amazon RDS

RDS es adecuado para modelos relacionales, joins y consultas SQL complejas. Sin embargo, para este caso agrega más carga operativa y no resulta necesario para el flujo principal de pedidos.

### Base de datos en una instancia EC2

Fue descartada por requerir administración manual, backups, escalabilidad y mantenimiento del servidor.

## Consecuencias positivas

- Baja latencia para lectura y escritura.
- Escalabilidad administrada.
- Modelo simple para consultar pedidos por clave.
- Buena integración con Lambda.
- Menor carga operativa.

## Consecuencias negativas

- Requiere diseñar correctamente las claves y los índices.
- No es ideal para consultas relacionales complejas.
- Para reportes avanzados puede requerir exportar datos a S3 o un sistema analítico.