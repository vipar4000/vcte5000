import os
import sys
import runpy

# The canonical test-user creation script lives in the repo root.
# Run it from here so both `python create_test_users.py` (from root)
# and `cd backend && python create_test_users.py` work identically.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_SCRIPT = os.path.join(ROOT_DIR, 'create_test_users.py')

sys.path.insert(0, ROOT_DIR)
runpy.run_path(ROOT_SCRIPT, run_name='__main__')
