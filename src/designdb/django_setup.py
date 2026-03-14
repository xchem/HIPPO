import django
from django.conf import settings


def configure_django(db_config, manage_models):

    if settings.configured:
        return

    if manage_models:
        # sqlite3 db, create and manage models
        database = {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': db_config,
        }
    else:
        # postgres, existing installation, don't touch
        database = {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': '...',
            'USER': '...',
            'PASSWORD': '...',
            'HOST': '...',
            'OPTIONS': {
                # sets the schema
                'options': '-c search_path=designdb'
            },
        }

    settings.configure(
        INSTALLED_APPS=[
            'designdb.apps.DesigndbConfig',
        ],
        DATABASES={'default': database},
        TIME_ZONE='UTC',
        USE_TZ=True,
        MANAGE_MODELS=manage_models,
    )

    django.setup()
