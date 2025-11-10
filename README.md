# Auth microservice (FastAPI)

Microservicio en Python para registro con correo y login con Google (id_token verification).

Requisitos
- Python 3.10+ (para desarrollo local)
- Docker y Docker Compose (para contenedores)

Instalación (desarrollo local)
1. Crear y activar un entorno virtual

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
```

2. Instalar dependencias

```powershell
pip install -r requirements.txt
```

3. Copiar `.env.example` a `.env` y rellenar `JWT_SECRET` y `GOOGLE_CLIENT_ID` si quieres usar Google login.

Uso (desarrollo)

```powershell
# Levantar server
uvicorn app.main:app --reload --port 8000
```

Uso con Docker
Para correr el microservicio con PostgreSQL en contenedores (recomendado):

```powershell
# Construir e iniciar contenedores
docker-compose up -d

# Ver logs
docker-compose logs -f auth-api

# Detener
docker-compose down
```

El servidor estará disponible en http://localhost:8000
- API docs: http://localhost:8000/docs
- Base de datos: PostgreSQL en localhost:5432 (usuario: postgres, contraseña: postgres)

Para producción, actualiza las variables de entorno en `docker-compose.yml` y usa `docker build` / `docker push` a tu registry.

Endpoints principales
- POST /register  -> {"email","password","full_name"}
- POST /login     -> form-data (username=email, password) -> devuelve JWT
- POST /google-login -> {"id_token": "..."} (id_token obtenido en frontend con Google)
- GET /me         -> Bearer <token>

Notas
- Para el login con Google, la app cliente debe solicitar un id_token (Google One Tap o Google Sign-In) y enviarlo a `/google-login`. El backend verifica el id_token con la librería `google-auth`.
- Este proyecto usa SQLite por defecto (archivo `dev.db`), pero puedes usar Supabase (Postgres) como base de datos.

Usar Supabase como base de datos
--------------------------------

Si quieres que la base de datos esté en Supabase (Postgres), sigue estos pasos:

1. Crea un proyecto en https://app.supabase.com/ y ve a "Settings -> Database -> Connection string" para copiar la connection string (Postgres).
2. En tu archivo `.env` establece `DATABASE_URL` con esa connection string. Ejemplo:

```text
DATABASE_URL=postgres://postgres:password@db.<region>.supabase.co:5432/postgres
```

3. Si además quieres usar Supabase Auth (recomendado para manejar social login como Google):
	- Configura los proveedores (Google) en la sección Authentication del panel de Supabase.
	- Añade `SUPABASE_URL` y `SUPABASE_ANON_KEY` a tu `.env` (o usa `SUPABASE_SERVICE_ROLE_KEY` en el servidor para tareas administrativas).
	- Con Supabase Auth el frontend suele gestionar el flujo de login/registro y el backend solo valida tokens.

Notas sobre la integración
- No es necesario modificar el código para usar Supabase como Postgres si pones la connection string en `DATABASE_URL` — SQLAlchemy conectará a la base de datos remota.
- Si usas Supabase Auth, puedes verificar tokens llamando a `GET {SUPABASE_URL}/auth/v1/user` con el token en Authorization, o validar el JWT localmente usando las claves/JWKS de Supabase.
- Para producción, asegúrate de usar `SUPABASE_SERVICE_ROLE_KEY` solo en el servidor y mantener las claves seguras.

WeasyPrint (generación de PDF)
--------------------------------

Este proyecto usa **Playwright** (headless browser) para generar PDFs a partir de sesiones. Playwright es más fácil de instalar en Windows que WeasyPrint ya que no requiere dependencias nativas de X11/Cairo/Fontconfig.

Instalación de Playwright
- Las dependencias Python se instalan con:

```powershell
pip install -r requirements.txt
```

- Luego instala los navegadores (Chromium, Firefox, etc.):

```powershell
playwright install chromium
```

(O `playwright install` para instalar todos los navegadores.)

Uso del endpoint PDF
- Guarda una sesión (POST /save-session) o usa una sesión existente.
- Llama `GET /sessions/{session_id}/pdf`. Devuelve `application/pdf` con el PDF generado.

Notas
- Playwright descarga automáticamente Chromium al ejecutar `playwright install`. Esta es una descarga única (~100 MB).
- Los PDFs se generan usando Chromium sin interfaz gráfica, por lo que los estilos CSS y fuentes se renderizan exactamente como en un navegador.
- En producción puedes cachear PDFs para no regenerarlos cada vez (implementable con Redis o similar).

Flujo recomendado: front hace autenticación con Google y llama al microservicio
-----------------------------------------------------------------------

Este proyecto asume que la autenticación con Google la realiza el frontend y que el frontend envía un `id_token` al endpoint `/google-login` del microservicio. A continuación tienes un ejemplo con la librería Google Identity Services (recomendada):

1) Cargar el script de Google en tu HTML/SPA:

```html
<script src="https://accounts.google.com/gsi/client" async defer></script>
```

2) Inicializar y renderizar el botón (ejemplo en JavaScript):

```javascript
function handleCredentialResponse(response) {
	// response.credential contiene el id_token JWT de Google
	const id_token = response.credential;

	// Enviar id_token al backend
	fetch("https://api.tu-dominio.com/google-login", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ id_token }),
	})
		.then(r => r.json())
		.then(data => {
			// data.access_token -> JWT emitido por tu microservicio
			// Guarda el token en memoria/almacenamiento seguro y redirige al usuario.
			const accessToken = data.access_token;
			// Guardar token de forma segura (ej. HttpOnly cookie sería ideal). Si usas localStorage, ten en
			// cuenta consideraciones de seguridad. Aquí mostramos el enfoque simple de SPA:
			if (accessToken) {
				// ejemplo: guardar en sessionStorage
				sessionStorage.setItem('access_token', accessToken);
				// Redirigir a la página que quieras (configurable). Evita poner el token en la URL.
				const redirectTo = sessionStorage.getItem('post_login_redirect') || '/dashboard';
				window.location.href = redirectTo;
			} else {
				console.error('No access_token returned from backend', data);
			}
		})
		.catch(err => console.error(err));
}

window.onload = () => {
	google.accounts.id.initialize({
		client_id: "REPLACE_WITH_GOOGLE_CLIENT_ID",
		callback: handleCredentialResponse,
	});
	google.accounts.id.renderButton(
		document.getElementById("googleSignInDiv"),
		{ theme: "outline", size: "large" } // customization
	);
};
```

3) Flujo de backend
- El frontend obtiene el `id_token` y lo manda a `POST /google-login`.
- El endpoint `/google-login` (implementado en este microservicio) verifica el `id_token` usando la librería `google-auth` y, si es válido, crea o recupera el usuario en la base de datos (ahora puede ser Supabase Postgres si configuraste `DATABASE_URL`) y devuelve un JWT propio (`access_token`).

Alternativa: usar Supabase Auth en el frontend
- Si en lugar de verificar directamente el `id_token` prefieres delegar la autenticación a Supabase Auth, el frontend puede usar el cliente `@supabase/supabase-js` para hacer el login con Google y luego enviar el access token de Supabase al backend. En ese caso el backend deberá validar el token contra Supabase (por ejemplo llamando a `GET {SUPABASE_URL}/auth/v1/user` o validando el JWT con JWKS).

En resumen: el flujo que pediste (frontend hace auth con Google) está soportado por `/google-login`. Simplemente asegúrate de que el frontend obtenga `id_token` y lo envíe al microservicio; la base de datos puede permanecer en Supabase si así lo configuras.
