OUTDIR ?= diff-out

venv:
	python3 -m venv venv
	. venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

run:
ifndef OPENAPI
	$(error OPENAPI is not set. Usage: make run OPENAPI=... DIFF=...)
endif
ifndef DIFF
	$(error DIFF is not set. Usage: make run OPENAPI=... DIFF=...)
endif
	. venv/bin/activate && python generate_curl_files.py $(OPENAPI) $(DIFF) -o $(OUTDIR)

clean:
	rm -rf $(OUTDIR)

deactivate:
	deactivate || true
