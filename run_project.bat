python -m venv venv
call venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_data --count 100
python manage.py collectstatic --noinput
python manage.py runserver
