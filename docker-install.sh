#!/bin/bash

echo "🚀 Atualizando pacotes..."
sudo apt update && sudo apt upgrade -y

echo "🐳 Instalando Docker..."
sudo apt install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

sudo mkdir -m 0755 -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/$(. /etc/os-release && echo "$ID")/gpg | \
sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo \  "deb [arch=$(dpkg --print-architecture) \  signed-by=/etc/apt/keyrings/docker.gpg] \  https://download.docker.com/linux/$(. /etc/os-release && echo "$ID") \  $(lsb_release -cs) stable" | \sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "🔧 Adicionando $USER ao grupo docker..."
sudo usermod -aG docker $USER

echo "✅ Habilitando Docker no boot..."
sudo systemctl enable docker
sudo systemctl start docker

echo "🌐 Instalando Portainer..."
docker volume create portainer_data
docker run -d -p 9000:9000 -p 9443:9443 \    --name=portainer \    --restart=always \    -v /var/run/docker.sock:/var/run/docker.sock \    -v portainer_data:/data \    portainer/portainer-ce

echo "🔥 Docker e Portainer instalados com sucesso!"
echo "🌐 Acesse o Portainer em http://IP_DO_SERVIDOR:9000"
