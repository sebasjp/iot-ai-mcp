# Dashboard del rack (Juan)

Next.js con exportación estática (`output: "export"`) servida desde S3. Parte del dashboard de la
Práctica 3, adaptado a la Actividad 4:

- **Tres tarjetas de modelo** (`rack01-env`, `rack01-vibration`, `rack01-camera`): clase actual,
  confianza, probabilidad por clase con la marca del umbral de 0,6, latencia de inferencia en el
  dispositivo y estado en línea. Ambiente muestra temperatura/humedad (ASHRAE); puerta, la última foto.
- **Historial**: línea de tiempo de las predicciones de los tres modelos con las alarmas marcadas,
  gráficas de temperatura y humedad, y CSV con todas las predicciones (1 h, 6 h o 24 h).
- **Alarmas** (últimas 24 h): las que guardó la Lambda `rack-alarmas` (`device_id` `rack01-alarmas`),
  con prioridad y estado del envío a Telegram.
- **Aperturas de la puerta**: fotos que sube la Pi a `rack-fotos-041118530115`.

Datos: `GET /readings` del API Gateway (Lambda `rack-api`), polling cada 10 s. Se ocultan las filas
con `"prueba": true`.

```bash
cp .env.example .env.local     # API y bucket de fotos (no son secretos)
npm ci && npm run dev          # http://localhost:3000
npm run build                  # genera out/
aws s3 sync out/ s3://rack-monitor-dashboard-041118530115 --delete --profile escritura
```

Sitio: http://rack-monitor-dashboard-041118530115.s3-website-us-east-1.amazonaws.com/
