

cd deployment/ansible
ansible-playbook setup_solarmax-mqtt.yaml -i inventory.ini

influx config create --config-name INFLUX3 -host-url https://localhost --org solarsmart --token Rm5DcGoDMJmP4Ft94Is6PI-cnkeHODzJshiDyWM2J7NUzucKay4EVqDOPniTMQIoQRUoLeSCZrNHOXLbrSO32A== --active
