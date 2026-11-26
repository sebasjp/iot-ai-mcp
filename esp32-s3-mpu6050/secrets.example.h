// Copiar este archivo como secrets.h y completar los valores.
// secrets.h NO se sube al repositorio (está en .gitignore).
#pragma once

#define WIFI_SSID       "nombre-de-la-red"
#define WIFI_PASSWORD   "clave-de-la-red"

// aws iot describe-endpoint --endpoint-type iot:Data-ATS
#define AWS_IOT_ENDPOINT "xxxxxxxxxxxxxx-ats.iot.us-east-1.amazonaws.com"

// Amazon Root CA 1 (AmazonRootCA1.pem)
static const char AWS_CERT_CA[] = R"EOF(
-----BEGIN CERTIFICATE-----
...
-----END CERTIFICATE-----
)EOF";

// Certificado del Thing rack01-vibration (xxxx-certificate.pem.crt)
static const char AWS_CERT_CRT[] = R"EOF(
-----BEGIN CERTIFICATE-----
...
-----END CERTIFICATE-----
)EOF";

// Llave privada del Thing rack01-vibration (xxxx-private.pem.key)
static const char AWS_CERT_PRIVATE[] = R"EOF(
-----BEGIN RSA PRIVATE KEY-----
...
-----END RSA PRIVATE KEY-----
)EOF";
