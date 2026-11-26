"""Subida de fotos a S3 en segundo plano (la última y las de cada apertura).

Credenciales: usuario IAM rack-pi-fotos (solo s3:PutObject en <bucket>/rack01/*), leídas por boto3
de AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY en el .env (nunca en git).
Si S3_BUCKET está vacío, la subida queda desactivada y el servicio sigue igual.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


class SubidorFotos:
    def __init__(self, bucket: str, prefijo: str):
        self.bucket, self.prefijo = bucket, prefijo.strip("/")
        self.activo = bool(bucket)
        self._hilo = ThreadPoolExecutor(max_workers=1)  # una subida a la vez, sin frenar el ciclo
        self._pendiente_ultima = None
        if self.activo:
            import boto3  # solo si se usa: arranca más rápido sin S3
            from botocore.config import Config

            self._s3 = boto3.client("s3", config=Config(connect_timeout=5, read_timeout=10,
                                                        retries={"max_attempts": 2}))

    def clave(self, nombre: str) -> str:
        return f"{self.prefijo}/{nombre}"

    def subir_ultima(self, foto: Path) -> None:
        """Sube la foto como <prefijo>/ultima.jpg. Si la anterior aún no termina, se salta."""
        if not self.activo or (self._pendiente_ultima and not self._pendiente_ultima.done()):
            return
        datos = foto.read_bytes()  # se lee ya: el archivo puede cambiar en el siguiente ciclo
        self._pendiente_ultima = self._hilo.submit(self._subir, datos, self.clave("ultima.jpg"),
                                                   "no-cache")

    def subir_apertura(self, foto: Path) -> str | None:
        """Sube una foto de apertura; devuelve la clave en S3 (para el payload) o None."""
        if not self.activo:
            return None
        clave = self.clave(f"aperturas/{foto.name}")
        self._hilo.submit(self._subir, foto.read_bytes(), clave, "max-age=86400")
        return clave

    def _subir(self, datos: bytes, clave: str, cache: str) -> None:
        try:
            self._s3.put_object(Bucket=self.bucket, Key=clave, Body=datos,
                                ContentType="image/jpeg", CacheControl=cache)
        except Exception as e:  # noqa: BLE001 — sin red no se cae el servicio
            print(f"[S3] No se pudo subir {clave}: {e!r}")

    def cerrar(self) -> None:
        self._hilo.shutdown(wait=False, cancel_futures=True)
