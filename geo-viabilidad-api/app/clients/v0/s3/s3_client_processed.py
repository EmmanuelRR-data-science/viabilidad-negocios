from app.clients.v0.s3.s3_client_raw import generar_presigned_url
from app.schemas.v0.s3.s3_domain_schemas import UrlDescargaSegura


def obtener_url_descarga(
    bucket: str,
    key: str,
    filename: str,
    expires_in: int = 600,
) -> UrlDescargaSegura:
    dto = generar_presigned_url(bucket, key, filename, expires_in)
    return UrlDescargaSegura(url=dto.url, validez_segundos=dto.expires_in)
