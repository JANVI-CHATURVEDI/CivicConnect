python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_data --count 100
python manage.py collectstatic --noinput || true
python manage.py runserver
