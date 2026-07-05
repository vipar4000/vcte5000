#!/bin/bash
set -e

echo "=========================================="
echo "  DEPLOY R Car Rogil ERP - OVHcloud"
echo "=========================================="

# 1. Actualizar sistema
echo "[1/8] Actualizando sistema..."
sudo apt update && sudo apt upgrade -y

# 2. Instalar Docker
echo "[2/8] Instalando Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker $USER
    echo "Docker instalado. Ejecuta 'newgrp docker' despues de este script."
else
    echo "Docker ya instalado."
fi

# 3. Instalar Docker Compose
echo "[3/8] Instalando Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
else
    echo "Docker Compose ya instalado."
fi

# 4. Instalar certbot
echo "[4/8] Instalando certbot..."
sudo apt install certbot -y

# 5. Clonar repositorio
echo "[5/8] Clonando repositorio..."
cd /home/$USER
if [ -d "eurocar" ]; then
    echo "Directorio eurocar ya existe, actualizando..."
    cd eurocar
    git pull
else
    # REEMPLAZAR con la URL real del repositorio
    git clone https://github.com/TU_USUARIO/eurocar.git eurocar
    cd eurocar
fi

# 6. Cambiar contrasenas por defecto
echo "[6/8] Configurando variables de entorno..."
echo ""
echo "IMPORTANTE: Edita .env.production con contrasenas seguras:"
echo "  - SECRET_KEY (genera una nueva)"
echo "  - POSTGRES_PASSWORD"
echo ""
echo "Comando para generar SECRET_KEY:"
echo "  python3 -c \"import secrets; print(secrets.token_urlsafe(50))\""
echo ""

# 7. Construir y levantar (sin SSL primero)
echo "[7/8] Construyendo y levantando servicios..."
docker-compose -f docker-compose.prod.yml up -d --build

# 8. Ejecutar migraciones y configurar Django
echo "[8/8] Configurando Django..."
sleep 10  # Esperar a que PostgreSQL este listo
docker-compose -f docker-compose.prod.yml exec backend python manage.py migrate
docker-compose -f docker-compose.prod.yml exec backend python manage.py collectstatic --noinput

echo ""
echo "=========================================="
echo "  SERVIDOR LEVANTADO (HTTP)"
echo "=========================================="
echo ""
echo "Siguiente paso: configurar DNS en DonDominio"
echo "  A     @      79.143.89.97"
echo "  A     www    79.143.89.97"
echo ""
echo "Despues de que el DNS propague, ejecuta:"
echo "  sudo certbot certonly --standalone -d rcarrogil.com -d www.rcarrogil.com"
echo "  sudo mkdir -p docker/nginx/ssl"
echo "  sudo cp /etc/letsencrypt/live/rcarrogil.com/fullchain.pem docker/nginx/ssl/"
echo "  sudo cp /etc/letsencrypt/live/rcarrogil.com/privkey.pem docker/nginx/ssl/"
echo "  sudo chmod 644 docker/nginx/ssl/fullchain.pem"
echo "  sudo chmod 600 docker/nginx/ssl/privkey.pem"
echo "  cp docker/nginx/prod-http.conf docker/nginx/prod-http.conf.bak"
echo "  mv docker/nginx/prod.conf docker/nginx/prod-http.conf"
echo "  mv docker/nginx/prod.conf docker/nginx/prod.conf"
echo "  # Editar prod.conf: reemplazar la linea listen 80 por la version con SSL"
echo "  docker-compose -f docker-compose.prod.yml restart nginx"
echo ""
echo "Para crear superusuario:"
echo "  docker-compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser"
