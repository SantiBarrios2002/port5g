.PHONY: up demo down logs subscribers
up:
	docker compose up -d mongo nrf scp ausf udm udr pcf bsf nssf amf smf upf-control upf-vision upf-iot
	sleep 8
	$(MAKE) subscribers
	docker compose up -d gnb
subscribers:
	docker compose exec -T udr sh /etc/open5gs/subscribers.sh
demo:
	bash demo.sh
down:
	docker compose --profile demo down -v
logs:
	docker compose logs -f amf smf nssf pcf
