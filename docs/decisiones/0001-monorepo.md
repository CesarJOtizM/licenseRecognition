# 0001. Un solo repositorio (monorepo) para todo el sistema

- **Estado:** Aceptado
- **Fecha:** 2026-10-04

## Contexto

El sistema tiene varias piezas: la web (Next.js), la API (FastAPI), el equipo local de la portería (edge agent) y el trabajo de ML. Algunas comparten contratos; por ejemplo, el evento `PlateRead` lo produce el equipo local y lo consume la API. El proyecto lo desarrolla una sola persona y es para aprender.

## Opciones

1. **Monorepo (un repositorio con todas las piezas):** un cambio en un contrato compartido toca productor y consumidor en el mismo commit; hay una sola historia que seguir. La desventaja es que el repositorio crece y hay que cuidar que cada pieza siga siendo independiente.
2. **Un repositorio por servicio:** cada pieza se versiona y despliega por separado. Para una persona significa coordinar cambios entre varios repositorios y publicar los contratos como paquetes.

## Decisión

Monorepo, con la estructura del plan: `apps/web`, `services/api`, `services/edge-agent`, `ml`, `infra` y `docs`. Cada servicio tiene su propio `README.md` y sus propias dependencias, para que pueda ejecutarse y probarse por separado.

## Consecuencias

- Los contratos compartidos pueden vivir en el mismo repositorio sin publicarlos como paquetes.
- Cada servicio debe poder ejecutarse solo desde su carpeta; no se permite importar código de otro servicio por rutas relativas.
- Si más adelante el equipo local se instala en muchas porterías, se puede extraer a su propio repositorio.
