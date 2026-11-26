# Inconvenientes y soluciones

Registro de cada problema en el momento en que aparece, con su causa y lo que se hizo. Alimenta la
sección "Inconvenientes" del README.

## Modelo de imágenes (Juan)

### 2026-11-25 · Error de prueba: foto de mala calidad (`WIN_20261125_00_22_34_Pro_2.jpg`)

- **Qué pasó:** una puerta abierta se predijo como cerrada (modelo v3, float32).
- **Causa:** la foto salió movida e inclinada, con un dedo en el cuadro y casi solo pared. Es un
  problema de captura, no del modelo.
- **Solución:** se borra del dataset por calidad. Se habría borrado igual si el modelo hubiera
  acertado: el criterio es la calidad de la foto, no el resultado. Se revisan y borran con el mismo
  criterio las demás fotos movidas o con dedos.

### 2026-11-25 · Error de prueba: puerta corrediza entreabierta (`WIN_20261125_00_19_15_Pro_2.jpg`)

- **Qué pasó:** un clóset de puerta corrediza entreabierta se predijo como cerrado.
- **Causa:** solo una franja estrecha a la izquierda muestra el interior; a 96×96 px se parece a una
  puerta cerrada. Es una falla legítima del modelo.
- **Solución:** **se conserva** en el set de prueba, porque borrarla maquillaría las métricas
  (constitución III). Se documenta como caso límite. En la nueva captura con la cámara fija se toman
  fotos de la corrediza entreabierta por ambos lados.

### 2026-11-25 · Dos puertas abiertas "inciertas" (confianza < 0,6)

- **Qué pasó:** en la vista con umbral, dos fotos de `puerta_abierta` quedaron como *uncertain*. Una
  está muy borrosa y tomada de lado. En la otra, la puerta del clóset está entreabierta y al fondo se
  ve abierta la puerta de la habitación.
- **Causa:** la primera es un problema de captura. En la segunda hay dos puertas en el cuadro, así que
  el modelo aprendió "puerta abierta" en general y no "la puerta del rack".
- **Solución:** cámara fija con el encuadre cerrado sobre la puerta del rack, sin otras puertas al fondo,
  y reentrenar. En el servicio, una predicción incierta no cambia el estado ni dispara la alarma.

### 2026-11-25 · Desbalance de clases en el set de prueba

- **Qué pasó:** el set de prueba tiene 48 `puerta_abierta` contra 7 `puerta_cerrada`.
- **Efecto:** con 7 cerradas, cada acierto o error de esa clase mueve sus métricas más de 14 puntos.
  La precisión de `puerta_cerrada` (0,78) se apoya en solo 9 predicciones.
- **Solución:** en la nueva captura se toman 60–80 fotos **por clase** para equilibrar.

### 2026-11-25 · Fotos con la cámara en la mano y casi duplicadas

- **Qué pasó:** las fotos del dataset (tomadas por Julián) se capturaron con la cámara en la mano, y
  muchas tienen un segundo de diferencia entre sí.
- **Efecto:** (1) el ángulo y el encuadre varían, mientras que en la demo la cámara estará fija;
  (2) fotos casi idénticas pueden quedar unas en entrenamiento y otras en prueba (fuga de datos), y eso
  infla las métricas. La validación float32 dio 100 % y la prueba 96,4 %: la validación fue optimista.
- **Solución:** se despliega ya el modelo v3 para construir el flujo completo en la Pi. En paralelo se
  fija la cámara en su posición de la demo, se toman 60–80 fotos por clase (distintas aberturas y luces)
  y se reentrena. El modelo de la Pi se reemplaza por el nuevo.

### 2026-11-25 · El `.eim` de Edge Impulse no arranca en la Pi (glibc vieja)

- **Qué pasó:** al ejecutar el modelo exportado como *Linux (ARMv7)*: `GLIBC_2.34 not found`,
  `GLIBCXX_3.4.30 not found`.
- **Causa:** la Pi tiene Raspbian 10 Buster (glibc 2.28, GCC 8) y el `.eim` se compila contra
  bibliotecas de Debian 12 Bookworm (glibc 2.36, GCC 12).
- **Solución:** sin reinstalar el sistema. Se descargaron de Debian los paquetes armhf de Bookworm
  `libc6`, `libstdc++6` y `libgcc-s1`, se desempacaron (sin instalarlos) en `~/eim-libs`, y el `.eim`
  se arranca con el cargador dinámico de Bookworm y `--library-path` apuntando a esa carpeta
  (script `correr-eim.sh`). El resto del sistema sigue usando sus bibliotecas. Resultado: el modelo
  arranca y escucha en su socket.

### 2026-11-25 · El MCP (FastMCP) no se instala en la Pi con Buster

- **Qué pasó:** `uv sync` falló compilando `cffi` (falta `ffi.h`). Detrás venía un problema mayor:
  FastMCP depende de `cryptography`, cuyo wheel ARMv7 pide glibc ≥ 2.31 (Buster tiene 2.28), y
  compilarlo exige Rust y OpenSSL 3.
- **Solución:** sin reinstalar el sistema, con el mismo truco del `.eim`. Se usó Python 3.11, para
  que todo salga de wheels ya compilados de PyPI y piwheels, y se corre con el loader de Bookworm de
  `~/eim-libs`, al que se le agregaron `libffi8`, `libyaml` y `libssl3`. Script:
  `raspberry/mcp/instalar-en-buster.sh`; servicio: `rack-mcp-buster.service`. Probado con una llamada
  MCP real desde otro equipo: responde con datos de DynamoDB.

### 2026-11-25 · Disco de la Pi lleno (99 %) y bajo voltaje

- **Qué pasó:** quedaban 83 MB libres; `vcgencmd get_throttled` dio `0x50005` (bajo voltaje y CPU
  frenada en ese momento, y también antes).
- **Solución (disco):** se desinstalaron Wolfram Engine, Scratch 1/2/3 y LibreOffice, se hizo
  `autoremove` y se borraron la caché de Chromium y unos `.deb` de amd64 que no sirven en ARM.
  Quedaron 2,2 GB libres (68 %).
- **Solución (voltaje):** pendiente. Usar una fuente de 5 V / 2,5 A con un cable corto en lugar del
  USB del portátil.

## AWS (Juan)

### 2026-11-25 · Credenciales viejas de la AWS CLI en Windows

- **Qué pasó:** `aws sts get-caller-identity` devolvió `InvalidClientTokenId`.
- **Causa:** la access key guardada en el perfil `default` ya no era válida.
- **Solución:** se creó el usuario `claude-lectura` con `ReadOnlyAccess` y el perfil `lectura` de la
  CLI, solo para la revisión. Los cambios se hacen en la consola.

### 2026-11-25 · El thing de la cámara quedó con otro nombre

- **Qué pasó:** el thing se creó como `rack01-cam` (no `rack01-camera`) y su política como
  `rack-01-camera-policy` (no `rack01-camera-policy`).
- **Efecto:** ninguno en el funcionamiento: la política autoriza el clientId `rack01-camera` y el tópico
  `datacenter/rack01/camera`, que son los del contrato. AWS no permite renombrar things.
- **Solución:** se deja así y se documenta. La Pi se conecta con clientId y `device_id` `rack01-camera`.

### 2026-11-25 · La Lambda `rack-api` rechaza los `device_id` nuevos

- **Qué pasó:** el inventario mostró que `rack-api` valida `device_id` con `^rack\d{2}$`, así que
  rechaza `rack01-env`, `rack01-vibration` y `rack01-camera`.
- **Solución (hecha):** `GET /readings` acepta `^rack\d{2}(-(env|vibration|camera))?$` y
  `POST /command` sigue solo con `rack01`. Código en `aws/rack-api/`. Desplegado con un respaldo previo
  (versión 1 de la Lambda) y probado contra la API real. La versión que había en AWS era un poco
  más vieja que la del repo de la Práctica 3; se partió de la del repo.
