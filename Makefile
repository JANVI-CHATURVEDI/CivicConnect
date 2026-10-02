run:
	python manage.py migrate && python manage.py runserver
seed:
	python manage.py seed_demo_data --count 250
test:
	DATABASE_URL=sqlite:///db_test.sqlite3 python manage.py test reports --noinput -v 1
lint:
	ruff check . || true
