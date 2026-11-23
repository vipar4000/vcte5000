# Guía: configurar Cloudflare R2 para las fotos y PDFs

**Para qué sirve**: hoy el disco de Render es **efímero**. Cada despliegue borra
las fotos de los vehículos, las facturas en PDF y los contratos. Esta guía
conecta el ERP a un bucket de Cloudflare R2 para que los archivos **no se
pierdan nunca**.

**Cuándo hacerlo**: antes de la prueba de extremo a extremo, para no volver a
subir fotos después de cada despliegue.

**Coste**: el plan gratuito de R2 incluye 10 GB de almacenamiento y no cobra
tráfico de salida. Para este ERP sobra.

---

## Antes de empezar

Necesitas:

- La cuenta de Cloudflare donde está el dominio `rogil.co`.
- Acceso al panel de Render del servicio `eurocar-staging`.
- 15 minutos.

Los archivos actuales (fotos y PDFs subidos antes de hoy) **ya se han perdido**
en los últimos despliegues. Al final de la guía hay un apartado para volver a
subirlos.

---

## Paso 1. Crear el bucket

1. Entra en <https://dash.cloudflare.com> y elige tu cuenta.
2. En el menú lateral, abre **R2 Object Storage** (o **R2**).
3. Pulsa **Create bucket**.
4. Nombre: `rogil-media` (minúsculas, sin espacios).
5. Location: **Automatic** (o **Europe** si te deja elegir).
6. **Create bucket**.

> Anota el nombre exacto: lo usarás en `AWS_STORAGE_BUCKET_NAME`.

---

## Paso 2. Dar acceso público de lectura

Los archivos tienen que poder abrirse desde la web sin usuario ni contraseña.

1. Dentro del bucket, abre **Settings**.
2. En **Public access**, pulsa **Allow access** en la opción
   **R2.dev subdomain**.
3. Cloudflare te muestra una URL del tipo:

   ```
   https://pub-1a2b3c4d5e6f7g8h.r2.dev
   ```

   **Cópiala**: será tu `AWS_S3_CUSTOM_DOMAIN` (sin `https://`).

> `r2.dev` es perfecto para pruebas (staging). Para producción, Cloudflare
> recomienda un dominio propio (`media.rogil.co`) por velocidad y control; se
> configura en **Custom domains** dentro del mismo bucket y se usa igual en
> `AWS_S3_CUSTOM_DOMAIN`.

---

## Paso 3. Crear la clave de acceso (API token)

1. Vuelve a la pantalla principal de **R2**.
2. Arriba a la derecha, pulsa **Manage R2 API Tokens** (o **API Tokens**).
3. **Create API token**.
4. Nombre: `erp-rogil`.
5. Permissions: **Object Read & Write**.
6. Specify bucket: solo **rogil-media** (más seguro que todos los buckets).
7. TTL: **Forever** (o el que prefieras).
8. **Create API token**.

La pantalla te muestra **una sola vez**:

- **Access Key ID** → `AWS_S3_ACCESS_KEY_ID`
- **Secret Access Key** → `AWS_S3_SECRET_ACCESS_KEY`
- **Endpoint** del tipo
  `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` → `AWS_S3_ENDPOINT_URL`

Guarda los tres valores; el secreto no se puede volver a ver.

---

## Paso 4. Configurar las variables en Render

1. Entra en <https://dashboard.render.com>.
2. Abre el servicio **eurocar-staging**.
3. Menú **Environment** → **Add Environment Variable** y crea estas seis:

| Variable | Valor |
|---|---|
| `AWS_STORAGE_BUCKET_NAME` | `rogil-media` |
| `AWS_S3_ACCESS_KEY_ID` | el Access Key ID del paso 3 |
| `AWS_S3_SECRET_ACCESS_KEY` | el Secret Access Key del paso 3 |
| `AWS_S3_ENDPOINT_URL` | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |
| `AWS_S3_REGION_NAME` | `auto` |
| `AWS_S3_CUSTOM_DOMAIN` | `pub-1a2b3c4d5e6f7g8h.r2.dev` (sin `https://`) |

4. **Save changes**. Render redespliega solo; si no, pulsa
   **Manual Deploy → Clear build cache & deploy**.

> El código ya está preparado: `config/settings/staging.py` y
> `production.py` activan R2 en cuanto existe `AWS_STORAGE_BUCKET_NAME`, y
> `MEDIA_URL` pasa a apuntar al bucket. No hay que tocar nada más.

---

## Paso 5. Comprobar que funciona

1. En el ERP, entra en un vehículo en venta → **📢 Publicar** → sube una foto.
2. Abre la web pública y comprueba que la foto se ve.
3. Copia la URL de la imagen: debe empezar por `https://pub-....r2.dev/`.
4. En **Render → Shell**, ejecuta:

   ```bash
   python manage.py comprobar_imagenes_vehiculos
   ```

   Debe responder «Todas las fotos tienen su archivo en el almacenamiento».
5. Genera un PDF (por ejemplo, la factura de una venta) y ábrelo: tiene que
   descargarse bien.
6. Haz un despliegue de prueba (o espera al siguiente) y vuelve a comprobar:
   **la foto sigue ahí**. Eso confirma que ya no depende del disco.

---

## Paso 6. Recuperar las fotos perdidas

Las fotos que había antes de configurar R2 ya no existen en el servidor. Hay que
volver a subirlas:

1. Vehículos → abre el coche → **📢 Publicar**.
2. Sube la portada y las fotos de la galería.
3. Guarda.

Si quieres limpiar antes las referencias rotas (para que la galería no muestre
huecos), ejecuta en Render Shell:

```bash
python manage.py comprobar_imagenes_vehiculos --borrar-huerfanas
```

---

## Problemas frecuentes

**Las imágenes dan 404 pero el archivo está en R2**
→ Revisa `AWS_S3_CUSTOM_DOMAIN`: debe ser el dominio público (`pub-....r2.dev`
o `media.rogil.co`), sin `https://` y sin barra final.

**Error `SignatureDoesNotMatch` o `AccessDenied` al subir**
→ El token no tiene permiso de escritura sobre el bucket, o el
`AWS_S3_ENDPOINT_URL` no es el de tu cuenta. Vuelve a crear el token con
**Object Read & Write** sobre el bucket concreto.

**La web sigue mostrando `/media/...` en las URLs**
→ Falta `AWS_STORAGE_BUCKET_NAME` o el servicio no se ha redesplegado. En
Render, **Environment** → comprueba las variables → **Manual Deploy**.

**Se suben archivos pero no se ven**
→ El bucket no tiene acceso público activado (paso 2).

---

## Notas técnicas

- Las fotos se guardan con rutas como `vehiculos/1234ABC/foto.jpg`, las
  facturas en `facturas/` y los contratos en `contratos/`, todo dentro del
  bucket.
- `AWS_QUERYSTRING_AUTH=False`: las URLs son públicas y estables (sin firmas que
  caducan). El bucket **debe** ser de lectura pública.
- No se usa `AWS_DEFAULT_ACL` (R2 ignora las ACL de S3); el acceso público se
  controla en el bucket.
- Para producción (cuando exista), repetir los pasos 1-4 en el servicio de
  producción con las mismas variables.
