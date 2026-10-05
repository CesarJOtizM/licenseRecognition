# Edge agent (equipo local de la portería)

Programa que corre en el mini-PC de la portería. Captura video (webcam, cámara IP o archivo), lee las placas, decide si abre, acciona la puerta y guarda los eventos en local para sincronizarlos con la API cuando hay internet.

"Edge" significa que el procesamiento ocurre en el borde de la red, junto a la cámara, y no en la nube. Así la puerta abre en menos de 1,5 s y sigue funcionando sin internet.

## Estado

Pendiente. En la fase 0, paso 2, se define el contrato `PlateRead`. El pipeline de visión llega en la fase 1.

## Cómo se ejecuta

Se documentará cuando exista el código.

## Cómo se prueba

Se documentará cuando exista el código.
