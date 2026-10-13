import sys, os, locale, traceback
try:
    import psycopg2
except Exception as e:
    print('Failed to import psycopg2:', e)
    sys.exit(1)
print('sys.getdefaultencoding():', sys.getdefaultencoding())
print('sys.getfilesystemencoding():', sys.getfilesystemencoding())
print('locale.getpreferredencoding():', locale.getpreferredencoding())
print('PYTHONUTF8 env:', os.environ.get('PYTHONUTF8'))
print('PGCLIENTENCODING env:', os.environ.get('PGCLIENTENCODING'))
print('LANG env:', os.environ.get('LANG'))
print('DATABASE_URL configured:', bool(os.environ.get('DATABASE_URL')))
print('psycopg2.__version__:', getattr(psycopg2, '__version__', None))
print('psycopg2.__file__:', getattr(psycopg2, '__file__', None))
try:
    psycopg2.connect(os.environ.get('DATABASE_URL'))
except Exception as e:
    traceback.print_exc()
    print('repr(e):', repr(e))
