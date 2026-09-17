import os
import sys

APP_ROOT = "/home/majikkuo/majikku_web"

sys.path.insert(0, APP_ROOT)
os.chdir(APP_ROOT)

from app import app as application