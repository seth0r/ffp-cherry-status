init:
	git submodule init
	git submodule update --remote
.PHONY: init

update:
	git pull
	git submodule update --remote
.PHONY: update
