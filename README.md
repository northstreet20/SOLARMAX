# solarmax
bring solarmax log to mqtt

## build docker
### build für macos (amd64)
docker buildx build . -t northstreet/solarmax:dev --push

### build für raspi (arm6):
docker buildx build . -t northstreet/solarmax:dev  --platform linux/arm/v6 --push

### build für raspi 5:
   docker buildx build . -t northstreet/solarmax:rpi_arm6 --platform linux/arm64/v8 --push
   (falls hängt, docker restart)

### build multiple: 
docker buildx create --name mybuilder
docker buildx use mybuilder
docker buildx inspect --bootstrap
docker buildx build -t northstreet/solarmax-mqtt:latest --platform linux/amd64,linux/arm/v6 --push .
docker buildx ls  

### deploy with ansible

cd deployment/ansible
ansible-playbook setup.yaml -i inventory.ini
