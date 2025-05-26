from setuptools import setup, find_packages

setup(
    name="edms",  # Имя твоего проекта
    version="1.0.0",  # Версия проекта
    description="A Django project for EDMS",  # Описание проекта
    author="Алехин Артур",  # Твоё имя
    author_email="isip_a.a.alyohin@mpt.ru",  # Твой email
    packages=find_packages(),  # Автоматически находит все Python-пакеты (docs, users и т.д.)
    include_package_data=True,  # Включает файлы, указанные в MANIFEST.in
    install_requires=[
        "asgiref>=3.8.1",
        "certifi>=2025.4.26",
        "Django>=5.2.1",
        "packaging>=25.0",
        "pillow>=11.2.1",
        "psycopg2-binary>=2.9.10",
        "python-decouple>=3.8",
        "pytz>=2025.2",
        "six>=1.17.0",
        "sqlparse>=0.5.3",
        "typing_extensions>=4.13.2",
        "tzdata>=2025.2",
        "urllib3>=2.4.0",
    ],
    entry_points={
        "console_scripts": [
            "my-django-project-manage = my_django_project.manage:main",  # Позволяет запускать manage.py
        ],
    },
)