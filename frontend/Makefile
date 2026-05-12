IMAGE ?= docker-registry.vinhmdev.com/mdevtrade-web:latest
NEXT_PUBLIC_API_URL ?= https://mdevtrade-api.vinhmdev.com
NEXT_PUBLIC_ASSISTANT_ID ?= agent

dev:
	npm run dev

build:
	docker build \
	  --build-arg NEXT_PUBLIC_API_URL=$(NEXT_PUBLIC_API_URL) \
	  --build-arg NEXT_PUBLIC_ASSISTANT_ID=$(NEXT_PUBLIC_ASSISTANT_ID) \
	  -t $(IMAGE) .

push: # production run at port 3000
	docker push $(IMAGE)
