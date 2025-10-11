	•	git fetch –all –prune && git rebase origin/main
	•	git grep -n ‘<<<<<<<|=======|>>>>>>>’   # должно быть пусто
	•	python -m pip install -U pip && pip install -r requirements.txt -r requirements-dev.txt
	•	make test
	•	make ui   # или npm ci && npm run build
