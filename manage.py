#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portal.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Não foi possível importar o Django. "
            "Certifique-se de que está no virtualenv correto."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
